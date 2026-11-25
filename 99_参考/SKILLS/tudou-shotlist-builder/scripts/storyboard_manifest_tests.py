"""Offline storyboard contract regression tests. No paid generation."""
import copy
import unittest

from storyboard_manifest_lint import validate


def fixture():
    shots = [dict(shot_id='S1', scene_id='SC1', unit_id='H3-001', start=0, end=6,
                  source_beats=['B1'], dialogue='我会回来。'),
             dict(shot_id='S2', scene_id='SC1', unit_id='H3-001', start=6, end=12,
                  source_beats=['B2'], dialogue='')]
    panels = [dict(cell=i, shot_id=sid, at=t, frame_label=label, visual='看向门口。',
                   continuity='门在固定地标处。')
              for i, sid, t, label in [(1, 'S1', 0, 'S1a'), (2, 'S1', 3, 'S1b'), (3, 'S2', 6, 'S2')]]
    panels += [dict(cell=i, unused=True) for i in range(4, 10)]
    return dict(schema_version=1, scope_id='SC1', revision='r1', shots=shots,
                pages=[dict(page_id='P1', scene_id='SC1', revision='r1', aspect_ratio='16:9',
                            status='pending', image_path='', visual_qa=dict(passed=False, notes='尚未绘制'), panels=panels)])


class StoryboardTests(unittest.TestCase):
    def test_continuous_keyframes_count_shot_once(self):
        data = fixture()
        original = copy.deepcopy(data)
        errors, notices, runtime = validate(data)
        self.assertEqual(errors, [])
        self.assertEqual(runtime, 12)
        self.assertTrue(notices)
        self.assertEqual(data, original)

    def rejects(self, edit, expected):
        data = fixture()
        edit(data)
        errors, _, _ = validate(data)
        self.assertTrue(any(expected in e for e in errors), errors)

    def test_grid_count(self):
        self.rejects(lambda d: d['pages'][0]['panels'].pop(), '九格')

    def test_unknown_shot(self):
        self.rejects(lambda d: d['pages'][0]['panels'][0].update(shot_id='invented'), '未知镜号')

    def test_time_outside_shot(self):
        self.rejects(lambda d: d['pages'][0]['panels'][1].update(at=7), '超出')

    def test_reversed_time(self):
        self.rejects(lambda d: d['pages'][0]['panels'][1].update(at=0), '重复关键帧')

    def test_missing_coverage(self):
        self.rejects(lambda d: d['pages'][0]['panels'].__setitem__(2, dict(cell=3, unused=True)), '未绘制')

    def test_mixed_scene(self):
        self.rejects(lambda d: d['shots'][1].update(scene_id='SC2'), '跨越')

    def test_duplicate_shot(self):
        self.rejects(lambda d: d['shots'][1].update(shot_id='S1'), '重复镜号')

    def test_false_approval(self):
        self.rejects(lambda d: d['pages'][0].update(status='approved'), '实际图片')

    def test_missing_qa(self):
        self.rejects(lambda d: d['pages'][0].update(status='approved', image_path=__file__), '验收结论')

    def test_stale_revision(self):
        self.rejects(lambda d: d['pages'][0].update(revision='r0'), '版本不同')

    def test_timeline_gap(self):
        self.rejects(lambda d: d['shots'][1].update(start=7), '时间不连续')

    def test_nonfinite_time(self):
        self.rejects(lambda d: d['shots'][0].update(end=float('nan')), '时间区间无效')

    def test_bad_page_shape(self):
        self.rejects(lambda d: d['pages'].__setitem__(0, 'bad'), '不是对象')


if __name__ == '__main__':
    unittest.main(verbosity=2)
