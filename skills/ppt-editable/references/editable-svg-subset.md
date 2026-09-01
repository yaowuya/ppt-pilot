# Editable SVG subset

## Canvas and XML

Input must be UTF-8, use the SVG namespace, and declare the exact supported canvas. Parsing uses `defusedxml`. Declarations, DTDs, processing instructions, scripts, external URLs, comments inside metadata, foreign namespaces, and unconsumed data fail closed.

## Elements and attributes

Supported visible elements are `g`, `path`, `rect`, `circle`, `ellipse`, `line`, `polygon`, `polyline`, `text`, and nested `tspan`. Root `title` and `desc` are metadata, not shapes.

Attributes are allowlisted per element. `style`, `class`, `transform`, gradients, filters, animation, image, defs/use, clip/mask, foreignObject, unsupported units, and group opacity are forbidden.

Colors use `#RRGGBB` or `none`. Numeric values must be finite. Leaf opacity multiplies resolved fill/stroke opacity.

## Paths

Only absolute/relative `M/L/H/V/A/Z` commands are supported. The cursor lexer consumes every character and rejects unknown letters, malformed exponents, garbage, invalid arity/flags, trailing data, and non-finite values at the offending offset.

Arc rotation must be zero. SVG radius correction owns both DrawingML radii and sweep bounds. Coordinates and angles serialize through half-away-from-zero rounding.

## Groups

Every SVG `g` maps recursively to one `p:grpSp`; the root SVG is not a group. Empty production groups fail. Bounds are the retained descendant union, transforms use one absolute coordinate space, child order is z-order, and trace identity is written to `p:cNvPr/@descr`.

## Text

Every visible text line becomes one editable text box. Nested spans and tails are traversed recursively. Scalar `x` or line-changing `dy` starts a line; coordinate lists, `dx`, child `y`, mixed anchors, invalid whitespace modes, and non-finite values fail.

Default whitespace collapses XML spaces while retaining meaningful separators. `xml:space="preserve"` scopes recursively until an explicit default reset. Font, weight, fill, spacing, anchor, and source metadata inherit explicitly.

## Machine-only source IDs

Internal `SRC-<digits>` values may appear in `data-source-id`, storyboard mappings, verification evidence, and trace `descr` metadata. They must not appear in visible `<text>/<tspan>` content. The exact visible-text check is case-insensitive and word-bounded: `(?i)\bSRC-[0-9]+\b`.

A visible internal source ID fails as `svg_text_invalid` and blocks the complete deck. Human-readable citation names or URLs are allowed only when explicitly requested and contain no internal IDs. The converter never deletes text or substitutes an image.

## Failure behavior

Unsupported content produces a closed reason such as `svg_xml_invalid`, `svg_canvas_invalid`, `svg_element_unsupported`, `svg_attribute_unsupported`, `svg_external_reference`, `svg_path_invalid`, `svg_arc_rotation_unsupported`, `svg_group_empty`, `svg_coordinate_invalid`, or `svg_text_invalid`.

Any slide failure blocks candidate generation for the whole deck. There is no image fallback.
