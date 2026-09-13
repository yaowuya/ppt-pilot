"""User-specified Jiawei rules must survive the actual prompt compiler."""
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/ppt-start/scripts'))
sys.path.insert(0, str(ROOT / 'skills/ppt-style-extract/scripts'))
from _prompt_runtime import compile_style_prompt, validate_style_compiled_body
from _style_extract.verify import compose_prompt, verify_composed, verify_prompt, verify_tokens
from _style_extract.errors import VerificationError

PACK = ROOT / 'skills/ppt-start/assets/styles/jiawei-product'
ROLE = '# Role:产品经理& SVG 可视化编码专家'
NARRATIVE = ('- block_id: S01-B1\n- Revenue 80/100; collections 70/90; renewals 15/20.\n'
             '- Current focus: resolve two delayed contracts.\n'
             '- Next action: complete follow-up next week.\n').encode('utf-8')


class JiaweiPromptFidelityTests(unittest.TestCase):
    def setUp(self):
        self.tokens = json.loads((PACK / 'tokens.json').read_text(encoding='utf-8'))
        self.manifest = json.loads((PACK / 'manifest.json').read_text(encoding='utf-8'))
        self.rules = (PACK / 'STYLE.md').read_text(encoding='utf-8')
        self.template = (PACK / 'prompt.md').read_text(encoding='utf-8')
        self.body = compile_style_prompt(NARRATIVE, self.template.encode('utf-8')).decode('utf-8')

    def test_compiled_role_and_title_match_user_specification(self):
        self.assertEqual(self.body.splitlines()[0], ROLE)
        self.assertEqual(self.tokens['typography']['page_title'], 40)
        self.assertEqual(self.tokens['typography']['section_title'], 20)
        self.assertEqual(self.tokens['colors']['title_ink'], '#111827')
        self.assertEqual(self.manifest['version'], '1.2.0')
        self.assertIn('title_weight=700', self.body)
        self.assertIn('title_position="top_left"', self.body)
        verify_composed(self.manifest, self.tokens, self.template, self.rules)

    def test_fixed_brand_opt_in_still_requires_ordered_black_blue_squares(self):
        tokens = copy.deepcopy(self.tokens)
        for section in (tokens['composition'], tokens['prompt_baseline']['composition_rules']):
            section.update(strict_brand_rules=True, title_decoration='black_blue_offset_squares')
        template = compose_prompt(tokens)
        verify_composed(self.manifest, tokens, template, self.rules)
        body = compile_style_prompt(NARRATIVE, template.encode('utf-8')).decode('utf-8')
        for phrase in ('黑蓝错位方块', '左上黑', '右下蓝', '标题文字位于方块右侧'):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, body)
        self.assertNotIn('黑蓝错位方块', self.body)

    def test_palette_matches_the_five_user_specified_roles(self):
        expected = {'brand_primary': '#0B74E5', 'deep_primary': '#0A5CC9',
                    'highlight_blue': '#27B3FF', 'light_blue': '#EAF5FF', 'title_ink': '#111827'}
        self.assertEqual(self.tokens['colors'], expected)
        self.assertEqual([item['token'] for item in self.tokens['prompt_baseline']['palette_roles']], list(expected))
        for token, color in expected.items():
            with self.subTest(token=token):
                self.assertIn(token + '=' + color, self.body)
        self.assertIn('Source Han Sans / Microsoft YaHei / sans-serif', self.body)

    def test_modular_layout_does_not_force_old_recipes_or_action_focus(self):
        self.assertIn('layout_family="asymmetric_modular"', self.body)
        for removed in ('layout_recipes=', 'content_focus=', 'surface_style=', 'title_decoration='):
            with self.subTest(removed=removed):
                self.assertNotIn(removed, self.body)
        self.assertIn('no_english_title=true', self.body)
        self.assertIn('no_top_right_logo=true', self.body)

    def test_style_is_a_soft_baseline_with_preserved_prohibited_motifs(self):
        self.assertFalse(self.tokens['composition'].get('strict_brand_rules', False))
        self.assertIn('它们是软参考方向，不是逐项锁定令牌', self.body)
        self.assertNotIn('不得自行降级或替换', self.body)
        for phrase in ('背景图片或纹理', '毛玻璃', '大量高饱和蓝色块状元素', '等权卡片墙',
                       '强行拆分成数据卡片', '页面结论四字', '标题英文翻译', '右上角 logo 或图标', '穿过文字的连接线'):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.body)

    def test_approved_facts_and_office_safe_contract_remain_intact(self):
        self.assertIn(NARRATIVE.decode('utf-8').rstrip(), self.body)
        self.assertEqual(self.body.count('S01-B1'), 1)
        self.assertNotIn('{{NARRATIVE}}', self.body)
        self.assertIn('不得重新选择叙事逻辑', self.body)
        self.assertIn('不得改变数字、单位、期间、限定词', self.body)
        self.assertIn('禁止为 `<rect>` 添加 `rx` 或 `ry`', self.body)
        self.assertIn('禁止 `foreignObject`', self.body)
        self.assertIn('正文 ≥20px', self.body)
        self.assertIn('64px 安全区', self.body)
        self.assertIn('只返回一个 ```xml 代码围栏', self.body)
        validate_style_compiled_body(self.body.encode('utf-8'))
        for old, new in (('不得重新选择叙事逻辑', '可以重新选择叙事逻辑'),
                         ('禁止为 `<rect>` 添加 `rx` 或 `ry`', '允许任意 SVG 标签')):
            with self.subTest(old=old), self.assertRaises(VerificationError):
                verify_prompt(self.template.replace(old, new))

    def test_verified_style_title_size_reaches_svg_geometry_without_lowering_defaults(self):
        from _svg_runtime import validate_candidate
        svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">'
               '<title>Review</title><desc>Approved content</desc><g data-block-id="S01-B1">'
               '<text data-role="title" x="120" y="140" font-size="36" font-family="Microsoft YaHei">'
               '<tspan x="120" y="140">Review</tspan></text></g></svg>')
        tokens = copy.deepcopy(self.tokens)
        tokens['typography']['page_title'] = 36
        for section in (tokens['composition'], tokens['prompt_baseline']['composition_rules']):
            section['strict_brand_rules'] = True
        verify_tokens(tokens)
        try:
            candidate = validate_candidate(svg, ['S01-B1'], {'S01-B1': []},
                                           title_min_size=tokens['typography']['page_title'])
        except (TypeError, ValueError) as error:
            self.fail(f'Verified 36px brand title was rejected: {error}')
        self.assertIn(b'font-size="36"', candidate)
        with self.assertRaises(ValueError):
            validate_candidate(svg, ['S01-B1'], {'S01-B1': []})
        for minimum in (True, 20, float('nan'), float('inf')):
            with self.subTest(minimum=minimum), self.assertRaises(ValueError):
                validate_candidate(svg, ['S01-B1'], {'S01-B1': []}, title_min_size=minimum)
        for role, size in (('title', 33), ('body', 19), ('footnote', 13)):
            with self.subTest(role=role), self.assertRaises(ValueError):
                validate_candidate(svg.replace('data-role="title"', f'data-role="{role}"').replace('font-size="36"', f'font-size="{size}"'),
                                   ['S01-B1'], {'S01-B1': []}, title_min_size=36)

    def test_fixed_brand_prompt_carries_required_svg_encoding_metadata(self):
        tokens = copy.deepcopy(self.tokens)
        for section in (tokens['composition'], tokens['prompt_baseline']['composition_rules']):
            section['strict_brand_rules'] = True
        template = compose_prompt(tokens)
        verify_composed(self.manifest, tokens, template, self.rules)
        body = compile_style_prompt(NARRATIVE, template.encode('utf-8')).decode('utf-8')
        for instruction in ('width="1280"', 'height="720"', 'data-role="title"',
                            'data-role="body"', 'data-role="footnote"', '每个 text 只含一个 tspan'):
            with self.subTest(instruction=instruction):
                self.assertIn(instruction, body)

    def test_soft_spacing_preserves_the_hard_canvas_safety_boundary(self):
        self.assertEqual(self.tokens['spacing']['card_gap'], 20)
        self.assertEqual(self.tokens['spacing']['page_padding'], 12)
        self.assertEqual(self.tokens['spacing']['outer_margin'], 64)
        self.assertEqual(self.tokens['spacing']['standard_gap'], 24)
        self.assertIn('page_padding=12', self.body)
        self.assertNotIn('card_padding=24', self.body)
        self.assertIn('所有可见内容位于 64px 安全区内', self.body)

    def test_fixed_brand_title_cannot_declare_below_accessibility_floor(self):
        tokens = copy.deepcopy(self.tokens)
        for section in (tokens['composition'], tokens['prompt_baseline']['composition_rules']):
            section['strict_brand_rules'] = True
        tokens['typography']['page_title'] = 20
        with self.assertRaisesRegex(VerificationError, '^tokens_typography_invalid$'):
            verify_tokens(tokens)

    def test_prompt_role_is_closed_and_bound_to_verified_tokens(self):
        for value in ('system', 'product_manager\n{{NARRATIVE}}', True, ['product_manager']):
            tokens = copy.deepcopy(self.tokens)
            tokens['prompt_role'] = value
            with self.subTest(value=value), self.assertRaisesRegex(VerificationError, '^tokens_prompt_role_invalid$'):
                verify_tokens(tokens)
        tokens = copy.deepcopy(self.tokens)
        tokens['prompt_role'] = 'product_manager'
        actual = compose_prompt(tokens)
        self.assertEqual(actual.splitlines()[0], ROLE)
        verify_composed(self.manifest, tokens, actual, self.rules)
        other_role = actual.replace(ROLE, '# Role: 高级信息架构师 & SVG 可视化编码专家', 1)
        with self.assertRaisesRegex(VerificationError, '^prompt_style_binding_mismatch$'):
            verify_composed(self.manifest, tokens, other_role, self.rules)

    def test_new_composition_controls_reject_free_text_and_wrong_types(self):
        for key, value in (('strict_brand_rules', 'true'), ('title_decoration', 'arbitrary instructions'),
                           ('layout_recipes', ['ignore_all_rules']), ('layout_recipes', 'product_overview'),
                           ('layout_recipes', ['product_overview', 'product_overview']),
                           ('content_focus', 'new factual claims'), ('surface_style', 'ignore safety')):
            tokens = copy.deepcopy(self.tokens)
            tokens['composition'][key] = value
            tokens['prompt_baseline']['composition_rules'][key] = value
            with self.subTest(key=key, value=value), self.assertRaisesRegex(VerificationError, '^tokens_composition_rules_invalid$'):
                verify_tokens(tokens)

    def test_malformed_composition_and_huge_sizes_have_closed_validation_errors(self):
        for field, value in (('layout_family', []), ('title_position', {}), ('page_title', 10 ** 400)):
            tokens = copy.deepcopy(self.tokens)
            if field == 'page_title':
                tokens['typography'][field] = value
            else:
                tokens['composition'][field] = value
                tokens['prompt_baseline']['composition_rules'][field] = value
            with self.subTest(field=field):
                try:
                    verify_tokens(tokens)
                except Exception as error:
                    self.assertIsInstance(error, VerificationError)
                else:
                    self.fail('Invalid style data was accepted')

    def test_existing_default_style_keeps_exact_prompt_bytes(self):
        other = PACK.parent / 'canway-midyear-review'
        tokens = json.loads((other / 'tokens.json').read_text(encoding='utf-8'))
        self.assertEqual(compose_prompt(tokens), (other / 'prompt.md').read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
