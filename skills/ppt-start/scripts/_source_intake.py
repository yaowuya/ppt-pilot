"""Read-only, bounded extraction of semantic inventory from a PPTX package."""

import hashlib
import io
import posixpath
import zipfile
from pathlib import Path, PurePosixPath
from _xml_safety import parse_xml as _parse_xml


MAX_MEMBER_BYTES = 32 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024
MAX_MEMBERS = 10_000
# Includes ZIP headers and compressed-data overhead beyond the content budget.
MAX_SOURCE_BYTES = MAX_TOTAL_BYTES + 16 * 1024 * 1024

P = "http://schemas.openxmlformats.org/presentationml/2006/main"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PR = "http://schemas.openxmlformats.org/package/2006/relationships"
NS = {"p": P, "a": A, "r": R, "pr": PR}


def _safe_member_name(name):
    path = PurePosixPath(name)
    canonical = posixpath.normpath(name)
    if name.endswith("/"):
        canonical += "/"
    if (not name or "\\" in name or name.startswith("/") or path.is_absolute()
            or canonical != name or ":" in path.parts[0]
            or any(part in ("", ".", "..") for part in path.parts)):
        raise ValueError("unsafe package path: %s" % name)


def _read_member(archive, info, total):
    if info.flag_bits & 1:
        raise ValueError("encrypted ZIP members are not supported")
    if info.file_size > MAX_MEMBER_BYTES:
        raise ValueError("ZIP member exceeds 32 MiB budget: %s" % info.filename)
    with archive.open(info, "r") as stream:
        data = stream.read(MAX_MEMBER_BYTES + 1)
    if len(data) > MAX_MEMBER_BYTES:
        raise ValueError("ZIP member exceeds 32 MiB budget: %s" % info.filename)
    if total + len(data) > MAX_TOTAL_BYTES:
        raise ValueError("ZIP content exceeds 256 MiB total budget")
    return data


def _relationship_part(part):
    directory, filename = posixpath.split(part)
    return posixpath.join(directory, "_rels", filename + ".rels")


def _resolve_target(source_part, target):
    if not target or "\\" in target or target.startswith("//") or ":" in target:
        raise ValueError("unsafe relationship target: %s" % target)
    if target.startswith("/"):
        # OPC root-relative targets refer to ZIP members, never filesystem paths.
        resolved = target[1:]
        _safe_member_name(resolved)
        return resolved
    resolved = posixpath.normpath(posixpath.join(posixpath.dirname(source_part), target))
    if resolved == ".." or resolved.startswith("../"):
        raise ValueError("unsafe relationship target: %s" % target)
    _safe_member_name(resolved)
    return resolved


def _relationships(members, source_part, required=False):
    rel_part = _relationship_part(source_part)
    if rel_part not in members:
        if required:
            raise ValueError("missing relationships for %s" % source_part)
        return {}
    root = _parse_xml(members[rel_part], rel_part, "{%s}Relationships" % PR)
    result = {}
    for rel in root.findall("pr:Relationship", NS):
        rel_id = rel.get("Id")
        if not rel_id or rel_id in result or not rel.get("Type") or not rel.get("Target"):
            raise ValueError("invalid or duplicate relationship in %s" % rel_part)
        external = rel.get("TargetMode") == "External"
        if rel.get("TargetMode") not in (None, "Internal", "External"):
            raise ValueError("invalid relationship TargetMode in %s" % rel_part)
        target = rel.get("Target") if external else _resolve_target(source_part, rel.get("Target"))
        if not external and (target not in members or target.endswith("/")):
            raise ValueError("missing relationship target part: %s" % target)
        result[rel_id] = {
            "id": rel_id,
            "type": rel.get("Type"),
            "target": target,
            "external": external,
        }
    return result


def _validate_references(root, relationships, part):
    for node in root.iter():
        for key, value in node.attrib.items():
            if key.startswith("{%s}" % R) and value not in relationships:
                raise ValueError("missing referenced relationship %s in %s" % (value, part))


def _paragraph_text(paragraph):
    chunks = []
    for node in paragraph.iter():
        if node.tag == "{%s}t" % A:
            chunks.append(node.text or "")
        elif node.tag == "{%s}br" % A:
            chunks.append("\n")
        elif node.tag == "{%s}tab" % A:
            chunks.append("\t")
    return "".join(chunks)


def _paragraphs(root):
    return [_paragraph_text(p) for p in root.iter("{%s}p" % A) if _paragraph_text(p)]


def _tables(root):
    tables = []
    for table in root.iter("{%s}tbl" % A):
        rows = []
        for row in table.findall("a:tr", NS):
            cells = []
            for cell in row.findall("a:tc", NS):
                cells.append("\n".join(_paragraphs(cell)))
            rows.append(cells)
        tables.append({"rows": rows})
    return tables


def _object_id(element):
    marker = element.find(".//p:cNvPr", NS)
    if marker is None:
        return {}
    return {"object_id": marker.get("id"), "name": marker.get("name")}


def _objects(root, relationships):
    objects = []
    for element in root.iter():
        local = element.tag.rsplit("}", 1)[-1]
        object_type = None
        rel_ids = []
        if local == "pic":
            object_type = "image"
            rel_ids = [node.get("{%s}embed" % R) or node.get("{%s}link" % R)
                       for node in element.iter("{%s}blip" % A)]
        elif local == "oleObj":
            object_type = "ole"
            rel_ids = [element.get("{%s}id" % R)]
        elif local == "grpSp":
            object_type = "group"
        elif local == "graphicFrame":
            if element.find(".//a:tbl", NS) is not None:
                continue
            uri = " ".join(node.get("uri", "") for node in element.findall(".//a:graphicData", NS))
            object_type = "smartart" if "diagram" in uri else "chart" if "chart" in uri else "graphic"
            rel_ids = [value for node in element.iter() for key, value in node.attrib.items()
                       if key.startswith("{%s}" % R)]
        if object_type:
            base = {"type": object_type, **_object_id(element)}
            valid_ids = [rel_id for rel_id in rel_ids if rel_id]
            if not valid_ids:
                objects.append(base)
            for rel_id in valid_ids:
                item = dict(base, relationship_id=rel_id)
                relation = relationships.get(rel_id)
                if relation:
                    item["relationship_type"] = relation["type"]
                    item["external"] = relation["external"]
                objects.append(item)
    return objects


def extract_pptx(path):
    """Return a deterministic source inventory without modifying or extracting the deck."""
    source_path = Path(path)
    if source_path.suffix.lower() != ".pptx":
        raise ValueError("source must be a PPTX file; binary .ppt is not supported")
    try:
        if source_path.stat().st_size > MAX_SOURCE_BYTES:
            raise ValueError("source exceeds 272 MiB snapshot budget")
        with source_path.open("rb") as stream:
            source_bytes = stream.read(MAX_SOURCE_BYTES + 1)
        if len(source_bytes) > MAX_SOURCE_BYTES:
            raise ValueError("source exceeds 272 MiB snapshot budget")
    except OSError as error:
        raise ValueError("cannot read PPTX source: %s" % error) from error

    members = {}
    try:
        with zipfile.ZipFile(io.BytesIO(source_bytes), "r") as archive:
            infos = archive.infolist()
            if len(infos) > MAX_MEMBERS:
                raise ValueError("ZIP has more than 10000 members")
            names = set()
            total = 0
            for info in infos:
                _safe_member_name(info.filename)
                if info.filename in names:
                    raise ValueError("duplicate ZIP member: %s" % info.filename)
                names.add(info.filename)
                data = _read_member(archive, info, total)
                total += len(data)
                if info.filename.lower().endswith((".xml", ".rels")):
                    expected = "{%s}Relationships" % PR if info.filename.lower().endswith(".rels") else None
                    _parse_xml(data, info.filename, expected)
                members[info.filename] = data
    except (zipfile.BadZipFile, RuntimeError, OSError) as error:
        raise ValueError("invalid or unreadable PPTX package: %s" % error) from error

    presentation_part = "ppt/presentation.xml"
    if presentation_part not in members:
        raise ValueError("missing ppt/presentation.xml")
    presentation = _parse_xml(members[presentation_part], presentation_part, "{%s}presentation" % P)
    relations = _relationships(members, presentation_part, required=True)
    slide_list = presentation.find("p:sldIdLst", NS)
    if slide_list is None:
        raise ValueError("presentation has no slide list")
    listed_slides = slide_list.findall("p:sldId", NS)
    if not listed_slides:
        raise ValueError("presentation slide list is empty")

    slides = []
    all_warnings = []
    seen_ids = set()
    seen_parts = set()
    for position, slide_id in enumerate(listed_slides, 1):
        declared_id = slide_id.get("id")
        if not declared_id or declared_id in seen_ids:
            raise ValueError("missing or duplicate slide identifier")
        seen_ids.add(declared_id)
        rel_id = slide_id.get("{%s}id" % R)
        relation = relations.get(rel_id)
        if not relation or relation["external"] or not relation["type"].endswith("/slide"):
            raise ValueError("missing slide relationship: %s" % rel_id)
        part = relation["target"]
        if part in seen_parts:
            raise ValueError("duplicate slide part in presentation: %s" % part)
        seen_parts.add(part)
        if part not in members:
            raise ValueError("missing slide part: %s" % part)
        root = _parse_xml(members[part], part, "{%s}sld" % P)
        slide_relations = _relationships(members, part)
        _validate_references(root, slide_relations, part)
        notes = []
        for slide_relation in slide_relations.values():
            if not slide_relation["external"] and slide_relation["type"].endswith("/notesSlide"):
                notes_part = slide_relation["target"]
                if notes_part not in members:
                    raise ValueError("missing notes part: %s" % notes_part)
                notes_root = _parse_xml(members[notes_part], notes_part, "{%s}notes" % P)
                notes_relations = _relationships(members, notes_part)
                _validate_references(notes_root, notes_relations, notes_part)
                notes.extend(_paragraphs(notes_root))
        objects = _objects(root, slide_relations)
        texts = _paragraphs(root)
        warnings = []
        if objects:
            warnings.append({"code": "VISUAL_REVIEW_REQUIRED",
                             "message": "Embedded objects require visual review; full semantics were not extracted."})
        if not texts:
            warnings.append({"code": "NO_EXTRACTABLE_TEXT",
                             "message": "No extractable text was found; visually review this slide."})
        source_slide_id = "SRC-S%03d" % position
        for warning in warnings:
            all_warnings.append(dict(warning, source_slide_id=source_slide_id))
        slides.append({
            "source_slide_id": source_slide_id,
            "position": position,
            "part": part,
            "sha256": hashlib.sha256(members[part]).hexdigest(),
            "hidden": root.get("show") in ("0", "false", "False") or slide_id.get("show") in ("0", "false", "False"),
            "texts": texts,
            "tables": _tables(root),
            "notes": notes,
            "objects": objects,
            "warnings": warnings,
        })
    return {
        "schema_version": 1,
        "kind": "pptx_source_inventory",
        "source": {"name": source_path.name, "sha256": hashlib.sha256(source_bytes).hexdigest(),
                   "size_bytes": len(source_bytes)},
        "slide_count": len(slides),
        "slides": slides,
        "warnings": all_warnings,
    }
