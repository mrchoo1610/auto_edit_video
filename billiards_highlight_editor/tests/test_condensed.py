"""
Tests for the Full Match Condensed pipeline: strike gate, end-of-shot detection, clip merging,
rack segmentation, score timeline, and FFmpeg command construction.
"""

import unittest
import numpy as np

from billiards_highlight_editor import condensed as cd
from billiards_highlight_editor.condensed import Clip, CondensedConfig, Strike


def synth_audio(sr, duration, clicks):
    """Low noise + short 3 kHz bursts at the given (time, amplitude) pairs."""
    rng = np.random.default_rng(0)
    audio = rng.normal(0, 0.002, int(sr * duration)).astype(np.float32)
    n = int(0.01 * sr)
    burst = np.sin(2 * np.pi * 3000 * np.arange(n) / sr).astype(np.float32)
    for t, amp in clicks:
        i = int(t * sr)
        audio[i:i + n] += amp * burst
    return audio


class TestAudioStrikes(unittest.TestCase):
    def setUp(self):
        self.cfg = CondensedConfig()

    def test_followup_clicks_are_not_new_strikes(self):
        sr = self.cfg.sample_rate
        # cue strike at 5s, ball-ball clicks at 5.4 and 6.0, cushion at 6.9, next strike at 20s
        audio = synth_audio(sr, 30, [(5.0, 0.5), (5.4, 0.4), (6.0, 0.3), (6.9, 0.3), (20.0, 0.5)])
        peaks = cd.detect_peaks(cd.audio_envelope_db(audio, sr, self.cfg), self.cfg)
        strikes = cd.strike_candidates(peaks, self.cfg)
        self.assertEqual(len(strikes), 2)
        self.assertAlmostEqual(strikes[0].t, 5.0, delta=0.1)
        self.assertAlmostEqual(strikes[1].t, 20.0, delta=0.1)

    def test_silence_has_no_strikes(self):
        sr = self.cfg.sample_rate
        audio = synth_audio(sr, 10, [])
        peaks = cd.detect_peaks(cd.audio_envelope_db(audio, sr, self.cfg), self.cfg)
        self.assertEqual(cd.strike_candidates(peaks, self.cfg), [])


class TestShotEnd(unittest.TestCase):
    def setUp(self):
        self.cfg = CondensedConfig()

    @staticmethod
    def curve(moving_until, until, fps=10):
        return [(i / fps, 1.0 if i / fps < moving_until else 0.0) for i in range(int(until * fps))]

    def test_ends_when_table_goes_still(self):
        end, peak, capped = cd.detect_shot_end(self.curve(6.0, 20), 2.0, [2.0], self.cfg)
        self.assertAlmostEqual(end, 6.0, delta=0.15)
        self.assertEqual(peak, 1.0)
        self.assertFalse(capped)

    def test_audio_transient_resets_stillness(self):
        # table is still from 4.0s but a pocket drop rings at 4.3s -> shot ends later than 4.0
        end, _, _ = cd.detect_shot_end(self.curve(4.0, 20), 2.0, [2.0, 4.3], self.cfg)
        self.assertGreater(end, 4.3)

    def test_cap_when_never_still(self):
        end, _, capped = cd.detect_shot_end(self.curve(99, 60), 1.0, [1.0], self.cfg)
        self.assertTrue(capped)
        self.assertAlmostEqual(end, 1.0 + self.cfg.max_clip_sec, delta=0.3)


class TestBuildClips(unittest.TestCase):
    def setUp(self):
        self.cfg = CondensedConfig()

    def test_false_trigger_dropped_and_runout_merged(self):
        strikes = [Strike(10.0, -20, 99), Strike(13.0, -20, 99), Strike(40.0, -20, 99), Strike(80.0, -20, 99)]
        ends = {10.0: (11.0, 1.0, False),    # shot ends 11.0 -> clip [10 - pre_roll, 11 + tail]
                13.0: (14.0, 1.0, False),    # next shot starts before the first clip ends -> merged
                40.0: (40.5, 0.0, False),    # no motion: chalk tap
                80.0: (82.0, 1.0, False)}
        clips = cd.build_clips(strikes, lambda t: ends[t], self.cfg)
        self.assertEqual(len(clips), 2)
        self.assertEqual(clips[0].n_strikes, 2)
        self.assertAlmostEqual(clips[0].start, 10.0 - self.cfg.pre_roll_sec)
        self.assertAlmostEqual(clips[0].end, 14.0 + self.cfg.tail_sec)
        self.assertAlmostEqual(clips[1].start, 80.0 - self.cfg.pre_roll_sec)

    def test_break_gets_long_pre_roll(self):
        strikes = [Strike(30.0, -5, 60)]
        clips = cd.build_clips(strikes, lambda t: (36.0, 1.0, False), self.cfg, is_break_fn=lambda s: True)
        self.assertTrue(clips[0].is_break)
        self.assertAlmostEqual(clips[0].start, 30.0 - self.cfg.break_pre_roll_sec)

    def test_tail_sounds_of_running_shot_are_skipped(self):
        strikes = [Strike(10.0, -20, 99), Strike(12.5, -20, 99)]   # second is inside shot 1
        clips = cd.build_clips(strikes, lambda t: (15.0, 1.0, False), self.cfg)
        self.assertEqual(len(clips), 1)
        self.assertEqual(clips[0].n_strikes, 1)


class TestRacksAndScore(unittest.TestCase):
    def setUp(self):
        self.cfg = CondensedConfig()
        mk = lambda s, e, brk=False, snd=None: Clip(0, s, e, s + 2, is_break=brk, last_sound_t=snd or e - 1.5,
                                                    rack_check="ok" if brk else "")
        self.clips = [mk(0, 5),                        # warm-up, before first break
                      mk(10, 20, True), mk(30, 40), mk(50, 60, snd=57.0),    # rack 1
                      mk(100, 110, True), mk(120, 130, snd=127.0),           # rack 2
                      mk(200, 210, True), mk(220, 230)]                      # rack 3 (show match)

    def test_segment_racks(self):
        racks = cd.segment_racks(self.clips)
        self.assertEqual([(r["first_clip"], r["last_clip"]) for r in racks], [(1, 3), (4, 5), (6, 7)])
        self.assertEqual(racks[0]["win_t"], 57.0)

    def test_apply_winners_excludes_show_match(self):
        racks = cd.segment_racks(self.clips)
        warn = cd.apply_winners(racks, [1, 1, 2], race_to=2)
        self.assertEqual(warn, ["winners given after the match was already decided were ignored"])
        self.assertEqual([r["include"] for r in racks], [True, True, False])
        self.assertEqual(racks[1]["score_after"], [2, 0])

    def test_parse_winners(self):
        self.assertEqual(cd.parse_winners("P1, p2 1,2"), [1, 2, 1, 2])
        with self.assertRaises(ValueError):
            cd.parse_winners("P3")

    def test_score_switches_at_ball9_drop_only(self):
        racks = cd.segment_racks(self.clips)
        cd.apply_winners(racks, [1, 2], race_to=7)
        items = cd.build_render_plan(self.clips[1:6], [dict(r, first_clip=r["first_clip"] - 1,
                                                          last_clip=r["last_clip"] - 1) for r in racks[:2]],
                                     self.cfg)
        # rack 1: two clips keep 0-0, the clip holding win_t switches to 1-0 at 57.0 - 50.0 = 7.0s
        self.assertEqual([i.before for i in items[:3]], [(0, 0), (0, 0), (0, 0)])
        self.assertIsNone(items[0].after)
        self.assertEqual(items[2].after, (1, 0))
        self.assertAlmostEqual(items[2].switch_local, 7.0)
        # rack 2 starts from 1-0 and ends 1-1
        self.assertEqual(items[3].before, (1, 0))
        self.assertEqual(items[4].after, (1, 1))

    def test_missing_winner_is_rejected(self):
        racks = cd.segment_racks(self.clips)
        with self.assertRaises(ValueError):
            cd.build_render_plan(self.clips, racks, self.cfg)

    def test_manual_breaks_override_auto_detection(self):
        clips = [Clip(0, 0.1, 21.1, 2.1, is_break=True, rack_check="ok"), Clip(0, 60.0, 80.0, 62.0),
                 Clip(1, 5.0, 25.0, 7.0)]
        marked = cd.apply_manual_breaks(clips, ["18.8", "1:10.0"], self.cfg)
        # the first clip began 18 s before the break, so its earlier part stays behind as a separate clip
        self.assertEqual(len(clips), 4)
        self.assertFalse(clips[0].is_break)
        self.assertAlmostEqual(clips[0].end, 18.8 - self.cfg.break_pre_roll_sec)
        self.assertEqual(marked, [1, 3])
        self.assertFalse(clips[2].is_break)
        self.assertEqual(clips[1].strike_t, 18.8)
        self.assertAlmostEqual(clips[1].start, 18.8 - self.cfg.break_pre_roll_sec)
        self.assertEqual(clips[3].rack_check, "manual")

    def test_manual_wins_pick_last_clip_per_rack(self):
        racks = cd.segment_racks(self.clips)
        cd.apply_manual_wins(racks, self.clips, ["35.0", "127.0", "0:225.0"])
        self.assertEqual([r["last_clip"] for r in racks], [2, 5, 7])     # rack 1 now ends before the racking clip
        self.assertEqual(racks[0]["win_t"], 35.0)
        with self.assertRaises(ValueError):
            cd.apply_manual_wins(racks, self.clips, ["35.0"])

    def test_break_tokens_and_per_break_trim(self):
        tokens, trims = cd.parse_break_tokens("31.9, 497.3/20, 1:88.0/46")
        self.assertEqual(tokens, ["31.9", "497.3", "1:88.0"])
        self.assertEqual(trims, {(0, 497.3): 20.0, (1, 88.0): 46.0})
        mk = lambda s, strike, brk=False: Clip(0, strike - 2, strike + 5, strike, is_break=brk)
        clips = [mk(0, 440), mk(0, 480), mk(0, 490), mk(0, 500, True)]
        kept = cd.trim_before_breaks(clips, 0.0, {(0, 500.0): 15.0})
        self.assertEqual([c.strike_t for c in kept], [440, 480, 500])          # 490 is racking noise (within 15s)

    def test_break_without_clip_gets_inserted_and_overlap_trimmed(self):
        clips = [Clip(0, 0.0, 20.0, 5.0), Clip(0, 98.0, 110.0, 100.0)]
        marked = cd.apply_manual_breaks(clips, ["95.0"], self.cfg, end_fn=lambda src, t: (t + 8.0, 5.0, False))
        brk = [c for c in clips if c.is_break][0]
        self.assertEqual(brk.strike_t, 95.0)
        self.assertAlmostEqual(brk.start, 95.0 - self.cfg.break_pre_roll_sec)
        self.assertEqual(len(clips), 3)
        self.assertGreaterEqual(clips[2].start, brk.end)                       # next clip no longer repeats the break footage
        self.assertEqual(marked, [1])

    def test_break_inside_long_clip_keeps_previous_rack_part(self):
        clips = [Clip(0, 1598.0, 1743.0, 1615.0, capped=True, last_sound_t=1700.0)]
        cd.apply_manual_breaks(clips, ["1671.9"], self.cfg)
        self.assertEqual(len(clips), 2)
        head, brk = clips
        self.assertFalse(head.is_break)
        self.assertAlmostEqual(head.end, 1671.9 - self.cfg.break_pre_roll_sec)
        self.assertTrue(brk.is_break)
        self.assertAlmostEqual(brk.start, 1671.9 - self.cfg.break_pre_roll_sec)

    def test_wins_cut_racking_and_extend_short_clip(self):
        clips = [Clip(0, 0.0, 30.0, 5.0, is_break=True), Clip(0, 40.0, 55.0, 42.0), Clip(0, 60.0, 120.0, 62.0)]
        racks = cd.segment_racks(clips)
        cd.apply_manual_wins(racks, clips, ["58.0/59.0"], self.cfg)      # win falls in the gap between clips 2 and 3
        self.assertEqual(racks[0]["last_clip"], 1)                       # clip 2 is the last clip before the win
        self.assertEqual(clips[1].end, 59.0)                             # extended over the missing last shot
        racks = cd.segment_racks([Clip(0, 0.0, 30.0, 5.0, is_break=True), Clip(0, 40.0, 100.0, 42.0)])
        c2 = Clip(0, 40.0, 100.0, 42.0)
        cs = [Clip(0, 0.0, 30.0, 5.0, is_break=True), c2]
        cd.apply_manual_wins(racks, cs, ["50.0/52.0"], self.cfg)
        self.assertEqual(c2.end, 52.0)                                    # racking after the last shot is cut off

    def _miss_setup(self):
        mk = lambda s, e, **kw: Clip(0, s, e, s + 2, **kw)
        clips = [mk(0, 20, is_break=True), mk(30, 40), mk(50, 60), mk(70, 90, n_strikes=2), mk(100, 110), mk(200, 210)]
        racks = cd.segment_racks(clips)
        racks[0].update(last_clip=5, win_t=205.0, include=True, winner=1)
        return clips, racks

    def test_protected_clips(self):
        clips, racks = self._miss_setup()
        prot = cd.protected_clips(clips, racks, self.cfg)
        self.assertEqual(prot[0], "break")
        self.assertEqual(prot[3], "run-out")
        self.assertEqual(prot[5], "last clip of the rack")
        self.assertNotIn(4, prot)                              # ends at 110, win at 205: outside the 45 s window
        self.assertNotIn(1, prot)
        racks[0]["win_t"] = 120.0
        self.assertEqual(cd.protected_clips(clips, racks, self.cfg)[4], "9-ball window")

    def test_miss_filter_drops_only_when_count_rose(self):
        clips, racks = self._miss_setup()
        racks[0]["win_t"] = 500.0                                # nothing inside the 9-ball window
        counts = {1: ([5, 5, 6], [6, 6, 7]),                     # rose by 1: no pot -> drop
                  2: ([5, 5, 5], [4, 4, 4]),                     # fell: pot -> keep
                  4: ([5, 5, 5], [5, 5, 5])}                     # unchanged: uncertain -> keep
        dropped = cd.select_missed_clips(clips, racks, counts, self.cfg)
        self.assertEqual([d["clip"] for d in dropped], [1])

    def test_miss_filter_needs_enough_trustworthy_samples(self):
        clips, racks = self._miss_setup()
        racks[0]["win_t"] = 500.0
        self.assertEqual(cd.select_missed_clips(clips, racks, {1: ([5, 5], [9, 9, 9])}, self.cfg), [])   # too few before
        self.assertEqual(cd.select_missed_clips(clips, racks, {1: ([1, 1, 1], [9, 9, 9])}, self.cfg), [])  # too few balls seen

    def test_render_plan_skips_dropped_but_not_score_clip(self):
        clips, racks = self._miss_setup()
        racks[0].update(win_t=205.0)
        clips[1].skip = True
        clips[5].skip = True                                      # the clip carrying the score flip is always played
        cd.apply_winners(racks, [1], race_to=1)
        items = cd.build_render_plan(clips, racks, self.cfg)
        starts = [i.start for i in items]
        self.assertNotIn(30, starts)
        self.assertIn(200, starts)

    def test_match_state(self):
        self.assertEqual(cd.match_state(6, 6, 7), "HILL-HILL")
        self.assertEqual(cd.match_state(7, 3, 7), "FINAL")
        self.assertEqual(cd.match_state(6, 2, 7), "GAME_POINT")
        self.assertEqual(cd.match_state(2, 1, 7), "NORMAL")

    def test_handshake_extends_last_clip_within_duration(self):
        racks = cd.segment_racks(self.clips)
        cd.apply_winners(racks, [1, 1], race_to=2)
        items = cd.build_render_plan(self.clips, racks, self.cfg, durations={0: 135.0})
        last = [i for i in items if i.rack == 2][-1]
        self.assertEqual(last.end, 135.0)


class TestShotCapAndGates(unittest.TestCase):
    def setUp(self):
        self.cfg = CondensedConfig(shot_cap_sec=7.0, min_still_sec=1.0, min_run_sec=3.0)

    def test_cap_moves_on_to_a_strike_that_follows_closely(self):
        # strike 342.8, next strike 354.5 is within 15 s of the cap point (349.8): the budget moves to 354.5 + 7
        self.assertAlmostEqual(cd.effective_cap_sec(342.8, [342.8, 354.5, 382.7], self.cfg), 354.5 + 7 - 342.8)
        # a strike far beyond the window (382.7) does not extend it
        self.assertAlmostEqual(cd.effective_cap_sec(354.5, [354.5, 382.7], self.cfg), 7.0)

    def test_cap_off_when_zero(self):
        self.assertEqual(cd.effective_cap_sec(10.0, [10.0, 15.0], CondensedConfig()), 0.0)

    def test_busy_table_is_cut_at_the_cap_when_nothing_follows(self):
        samples = [(t / 10, 5.0) for t in range(0, 400)]          # always moving (player walking)
        end, _, capped = cd.detect_shot_end(samples, 1.0, [1.0], self.cfg, strike_times=[1.0])
        self.assertAlmostEqual(end, 1.0 + 7.0, delta=0.15)
        self.assertFalse(capped)

    def test_busy_table_is_not_cut_while_the_next_strike_is_coming(self):
        samples = [(t / 10, 5.0) for t in range(0, 400)]
        end, _, _ = cd.detect_shot_end(samples, 1.0, [1.0], self.cfg, strike_times=[1.0, 12.0])
        self.assertGreaterEqual(end, 12.0 + 7.0 - 0.15)

    def test_other_table_sound_has_no_ball_onset(self):
        cfg = CondensedConfig()
        still = [(100.0 + i / 10, 0.05) for i in range(-10, 20)]                 # table never changes (sound from another table)
        self.assertFalse(cd.has_ball_onset(still, 100.0, cfg))
        real = [(100.0 + i / 10, 0.05 if i < 0 else 0.7 + i * 0.05) for i in range(-10, 20)]   # still, then balls move
        self.assertTrue(cd.has_ball_onset(real, 100.0, cfg))

    def test_motion_that_was_already_there_is_not_an_onset(self):
        cfg = CondensedConfig()
        busy = [(100.0 + i / 10, 1.0) for i in range(-10, 20)]                    # a player walking: constant motion, no jump
        self.assertFalse(cd.has_ball_onset(busy, 100.0, cfg))

    def test_onset_check_can_be_turned_off(self):
        self.assertTrue(cd.has_ball_onset([], 5.0, CondensedConfig(min_onset_energy=0.0)))

    def test_rejected_trigger_does_not_hide_the_next_shot(self):
        strikes = [cd.Strike(100.0, -12.0, 30.0), cd.Strike(104.0, -20.0, 30.0)]
        ends = {100.0: (110.0, 0.0, False), 104.0: (108.0, 5.0, False)}          # first has no motion: rejected, ends at 110
        clips = cd.build_clips(strikes, lambda t: ends[t], CondensedConfig())
        self.assertEqual([round(c.strike_t) for c in clips], [104])


class TestMotionSegmentation(unittest.TestCase):
    def cfg(self, **kw):
        base = dict(motion_mode=True, pre_roll_sec=3.0, tail_sec=2.0, merge_gap_sec=0.0, move_energy=1.0,
                    move_low_energy=0.2, move_gap_sec=2.0, min_move_peak=3.0, move_smooth_sec=0.1)
        base.update(kw)
        return CondensedConfig(**base)

    def line(self, spans, total=100.0):
        """spans = [(t0, t1, energy)] on a 10 fps timeline, 0.02 elsewhere."""
        t = np.arange(0.0, total, 0.1)
        e = np.full_like(t, 0.02)
        for a, b, v in spans:
            e[(t >= a) & (t < b)] = v
        return np.stack([t, e], axis=1)

    def test_clip_runs_from_3s_before_to_2s_after_the_last_movement(self):
        clips = cd.clips_from_motion(self.line([(20.0, 24.0, 3.0)]), self.cfg())
        self.assertEqual(len(clips), 1)
        self.assertAlmostEqual(clips[0].start, 17.0, delta=0.15)
        self.assertAlmostEqual(clips[0].end, 26.0, delta=0.25)

    def test_slow_ball_is_not_cut_while_it_still_creeps(self):
        # strong hit, then a slow ball at 0.3 % for 6 s: the activity lasts until the ball is really still, + 2 s
        clips = cd.clips_from_motion(self.line([(20.0, 21.0, 4.0), (21.0, 27.0, 0.3)]), self.cfg())
        self.assertEqual(len(clips), 1)
        self.assertGreaterEqual(clips[0].end, 29.0 - 0.25)

    def test_pause_shorter_than_two_seconds_does_not_split(self):
        clips = cd.clips_from_motion(self.line([(20.0, 22.0, 3.0), (23.5, 25.0, 3.0)]), self.cfg(pre_roll_sec=0.0, tail_sec=0.0))
        self.assertEqual(len(clips), 1)

    def test_still_for_two_seconds_ends_the_activity(self):
        clips = cd.clips_from_motion(self.line([(20.0, 22.0, 3.0), (30.0, 32.0, 3.0)]), self.cfg(pre_roll_sec=0.0, tail_sec=0.0))
        self.assertEqual(len(clips), 2)

    def test_player_over_the_table_keeps_the_clip_open(self):
        # shot, then a player moving over the cloth at 0.5 % for 10 s: still one clip
        clips = cd.clips_from_motion(self.line([(20.0, 21.0, 4.0), (21.0, 31.0, 0.5)]), self.cfg())
        self.assertEqual(len(clips), 1)
        self.assertGreaterEqual(clips[0].end, 33.0 - 0.25)

    def test_movement_that_never_gets_strong_is_ignored(self):
        self.assertEqual(cd.clips_from_motion(self.line([(20.0, 30.0, 0.5)]), self.cfg()), [])


class TestAudit(unittest.TestCase):
    def setUp(self):
        self.mask = np.full((200, 300), 255, np.uint8)
        self.base = np.full((200, 300), 120, np.uint8)

    def test_identical_snapshots_have_no_difference(self):
        self.assertEqual(cd.snapshot_diff(self.base, self.base.copy(), self.mask), 0)

    def test_small_noise_is_ignored(self):
        noisy = self.base.copy()
        noisy[10, 10] = 200
        noisy[50:52, 60:62] = 200                          # a speck smaller than the 5x5 opening
        self.assertEqual(cd.snapshot_diff(self.base, noisy, self.mask), 0)

    def test_a_ball_sized_change_is_counted(self):
        moved = self.base.copy()
        moved[80:100, 100:120] = 20                       # ~400 px, a ball
        self.assertGreaterEqual(cd.snapshot_diff(self.base, moved, self.mask), 200)

    def test_change_touching_the_cloth_edge_is_ignored_as_a_whole(self):
        # an arm: starts at the edge of the cloth and reaches inside; none of it counts
        mask = np.zeros((200, 300), np.uint8)
        mask[20:180, 20:280] = 255                                   # the cloth, with a margin around it like in a real frame
        arm = self.base.copy()
        arm[20:80, 100:130] = 20                                     # enters over the top edge of the cloth
        arm[100:112, 140:150] = 20                                   # a fragment of the same arm, detached after the opening
        self.assertEqual(cd.snapshot_diff(self.base, arm, mask, edge_px=8), 0)

    def test_ball_inside_the_cloth_still_counts_with_the_edge_rule(self):
        moved = self.base.copy()
        moved[80:100, 100:120] = 20
        self.assertGreaterEqual(cd.snapshot_diff(self.base, moved, self.mask, edge_px=8), 200)

    def test_change_outside_the_cloth_mask_is_ignored(self):
        mask = np.zeros((200, 300), np.uint8)
        mask[:, :100] = 255
        moved = self.base.copy()
        moved[80:100, 200:220] = 20
        self.assertEqual(cd.snapshot_diff(self.base, moved, mask), 0)

    def _items(self):
        return [cd.RenderItem(0, 10.0, 20.0, 1, (0, 0)), cd.RenderItem(0, 30.0, 40.0, 1, (0, 0)),
                cd.RenderItem(0, 40.5, 50.0, 1, (0, 0)),     # 0.5 s later: not a cut worth checking
                cd.RenderItem(0, 70.0, 80.0, 2, (1, 0))]    # different rack: the racking was cut on purpose

    def test_audit_flags_changed_cuts_but_not_rack_changes(self):
        moved = self.base.copy()
        moved[80:100, 100:120] = 20
        frames = {(0, 19.8): self.base, (0, 30.2): moved,          # cut 1: the cloth changed
                  (0, 49.8): self.base, (0, 70.2): moved}          # cut 3: changed, but between racks
        rows = cd.audit_gaps(self._items(), lambda src, t: frames.get((src, round(t, 1))), self.mask, CondensedConfig(), intro_sec=4.0)
        self.assertEqual(len(rows), 2)                              # the 0.5 s join is skipped
        self.assertTrue(rows[0]["flagged"])
        self.assertAlmostEqual(rows[0]["out_time"], 14.0)           # 4 s intro + first clip 10 s
        self.assertTrue(rows[1]["rack_change"])
        self.assertFalse(rows[1]["flagged"])

    def test_missing_frame_is_not_flagged(self):
        rows = cd.audit_gaps(self._items()[:2], lambda src, t: None, self.mask, CondensedConfig())
        self.assertEqual(rows[0]["diff_px"], -1)
        self.assertFalse(rows[0]["flagged"])


class TestRestore(unittest.TestCase):
    def rows(self, **kw):
        r = {"out_time": 14.0, "flagged": True, "clip_from": 0, "clip_to": 1}
        r.update(kw)
        return [r]

    def test_flagged_cut_in_one_file_is_closed(self):
        clips = [cd.Clip(0, 10.0, 20.0, 12.0), cd.Clip(0, 30.0, 40.0, 33.0)]
        done = cd.restore_cuts(clips, self.rows(), {0: 100.0}, 30.0)
        self.assertEqual(clips[0].end, 30.0)                      # contiguous with the next clip now
        self.assertEqual(done[0]["restored_sec"], 10.0)

    def test_unflagged_cut_is_untouched(self):
        clips = [cd.Clip(0, 10.0, 20.0, 12.0), cd.Clip(0, 30.0, 40.0, 33.0)]
        cd.restore_cuts(clips, self.rows(flagged=False), {0: 100.0}, 30.0)
        self.assertEqual(clips[0].end, 20.0)

    def test_too_long_cut_is_only_reported(self):
        clips = [cd.Clip(0, 10.0, 20.0, 12.0), cd.Clip(0, 80.0, 90.0, 83.0)]
        done = cd.restore_cuts(clips, self.rows(), {0: 100.0}, 30.0)
        self.assertEqual(clips[0].end, 20.0)
        self.assertTrue(done[0]["skipped"])

    def test_cut_between_files_keeps_end_of_first_and_start_of_second(self):
        clips = [cd.Clip(0, 2650.0, 2670.0, 2655.0), cd.Clip(1, 12.0, 27.0, 15.0)]
        done = cd.restore_cuts(clips, self.rows(), {0: 2680.0, 1: 2680.0}, 30.0)
        self.assertEqual(clips[0].end, 2680.0)
        self.assertEqual(clips[1].start, 0.0)
        self.assertEqual(done[0]["restored_sec"], 22.0)           # 10 s left in file 1 + 12 s at the start of file 2

    def test_render_plan_remembers_the_clip_index(self):
        clips = [cd.Clip(0, 10.0, 20.0, 12.0), cd.Clip(0, 30.0, 40.0, 33.0)]
        racks = [{"rack": 1, "include": True, "winner": 1, "first_clip": 0, "last_clip": 1, "win_source": 0, "win_t": 38.0}]
        items = cd.build_render_plan(clips, racks, CondensedConfig())
        self.assertEqual([i.clip for i in items], [0, 1])


class TestZoom(unittest.TestCase):
    def test_default_zoom_crops_before_scaling_and_overlay(self):
        cfg = CondensedConfig(table_roi=[620, 520, 740, 290])
        crop = cd.zoom_crop(cfg)
        self.assertTrue(crop.startswith("crop=w=trunc(iw/1.300/2)*2:h=trunc(ih/1.300/2)*2"))
        self.assertIn("x=clip(990.0-iw/1.300/2\\,0\\,iw-iw/1.300)", crop)
        item = cd.RenderItem(0, 5.0, 15.0, 1, (0, 0))
        graph = (lambda c: c[c.index("-filter_complex") + 1])(
            cd.clip_command("ffmpeg", [], item, "s.mp4", "a.png", None, "o.mp4", cfg))
        self.assertLess(graph.index("crop="), graph.index("scale="))
        self.assertLess(graph.index("scale="), graph.index("overlay=0:0"))     # the scoreboard is not zoomed

    def test_zoom_center_overrides_table_roi_centre(self):
        cfg = CondensedConfig(table_roi=[620, 520, 740, 290], zoom_center=[952.0, 690.0])
        crop = cd.zoom_crop(cfg)
        self.assertIn("x=clip(952.0-iw/1.300/2", crop)
        self.assertIn("y=clip(690.0-ih/1.300/2", crop)
        self.assertNotIn("990.0", crop)

    def test_crop_window_keeps_the_whole_table_in_frame(self):
        # the same arithmetic as the ffmpeg expression, for the real table box 560..1345 x 535..855 on a 1920x1080 frame
        z, cx, cy, W, H = 1.3, 952.0, 690.0, 1920, 1080
        cw, ch = int(W / z / 2) * 2, int(H / z / 2) * 2
        x0 = min(max(cx - cw / 2, 0), W - cw)
        y0 = min(max(cy - ch / 2, 0), H - ch)
        self.assertTrue(x0 <= 560 and 1345 <= x0 + cw and y0 <= 535 and 855 <= y0 + ch)
        self.assertAlmostEqual((560 + 1345) / 2 - x0, cw / 2, delta=20)      # table is centred horizontally

    def test_zoom_off(self):
        self.assertEqual(cd.zoom_crop(CondensedConfig(zoom=1.0)), "")
        self.assertEqual(cd.zoom_crop(CondensedConfig(zoom=0)), "")

    def test_zoom_without_roi_is_centre_crop(self):
        self.assertEqual(cd.zoom_crop(CondensedConfig()), "crop=w=trunc(iw/1.300/2)*2:h=trunc(ih/1.300/2)*2,")


class TestScoreSfx(unittest.TestCase):
    def _graph(self, cfg, item):
        return (lambda c: c[c.index("-filter_complex") + 1])(
            cd.clip_command("ffmpeg", [], item, "s.mp4", "a.png", "b.png", "o.mp4", cfg))

    def test_click_is_mixed_in_at_the_score_jump(self):
        item = cd.RenderItem(0, 50.0, 60.0, 1, (0, 0), (1, 0), 7.0)
        g = self._graph(CondensedConfig(), item)
        self.assertIn("adelay=7000|7000", g)
        self.assertIn("amix=inputs=2:duration=first:normalize=0[a]", g)

    def test_no_click_without_jump_or_when_disabled(self):
        item = cd.RenderItem(0, 50.0, 60.0, 1, (0, 0), (1, 0), 7.0)
        self.assertNotIn("amix", self._graph(CondensedConfig(score_sfx=False), item))
        self.assertNotIn("amix", self._graph(CondensedConfig(), cd.RenderItem(0, 50.0, 60.0, 1, (0, 0))))

    def test_render_plan_records_rack_start_score(self):
        cfg = CondensedConfig()
        clips = [cd.Clip(0, 10.0, 20.0, 12.0), cd.Clip(0, 40.0, 50.0, 45.0), cd.Clip(0, 70.0, 80.0, 75.0)]
        racks = [{"rack": 1, "include": True, "winner": 1, "first_clip": 0, "last_clip": 1, "win_source": 0, "win_t": 48.0},
                 {"rack": 2, "include": True, "winner": 2, "first_clip": 2, "last_clip": 2, "win_source": 0, "win_t": 78.0}]
        items = cd.build_render_plan(clips, racks, cfg)
        self.assertEqual([i.rack_start for i in items], [(0, 0), (0, 0), (1, 0)])


class TestJoinMarking(unittest.TestCase):
    def test_contiguous_clips_have_no_join_between_them(self):
        cfg = CondensedConfig()
        clips = [cd.Clip(0, 10.0, 20.0, 12.0), cd.Clip(0, 20.0, 30.0, 25.0), cd.Clip(0, 50.0, 60.0, 55.0)]
        racks = [{"rack": 1, "include": True, "winner": 1, "first_clip": 0, "last_clip": 2,
                  "win_source": 0, "win_t": 58.0}]
        items = cd.build_render_plan(clips, racks, cfg)
        self.assertFalse(items[0].join_out)
        self.assertFalse(items[1].join_in)
        self.assertTrue(items[0].join_in)
        self.assertTrue(items[1].join_out)                    # gap 30 -> 50 is a real cut
        self.assertTrue(items[2].join_in)


class TestFFmpeg(unittest.TestCase):
    def test_clip_command_uses_enable_switch_and_fades(self):
        cfg = CondensedConfig()
        item = cd.RenderItem(0, 50.0, 60.0, 1, (0, 0), (1, 0), 7.0)
        cmd = cd.clip_command("ffmpeg", ["-c:v", "h264_nvenc"], item, "src.mp4", "a.png", "b.png", "o.mp4", cfg)
        graph = cmd[cmd.index("-filter_complex") + 1]
        self.assertIn("enable='lt(t,7.000)'", graph)
        self.assertIn("enable='gte(t,7.000)'", graph)
        self.assertIn("afade=t=out:st=9.800:d=0.200", graph)      # a real cut on both sides: long audio fade
        self.assertIn("fade=t=out:st=9.850:d=0.150", graph)
        self.assertIn("fade=t=in:st=0:d=0.150", graph)
        self.assertEqual(cmd.count("-i"), 3)
        self.assertEqual(cmd[cmd.index("-ss") + 1], "50.000")
        # every clip is aac 48 kHz stereo so intro/outro (silent stereo) can be concatenated with -c copy
        self.assertEqual(cmd[cmd.index("-ac") + 1], "2")
        self.assertEqual(cmd[cmd.index("-ar") + 1], "48000")
        self.assertEqual(cmd[-1], "o.mp4")

    def test_join_fades_apply_only_to_real_cuts(self):
        cfg = CondensedConfig()
        item = cd.RenderItem(0, 5.0, 15.0, 1, (0, 0), join_in=False, join_out=True)
        graph = (lambda c: c[c.index("-filter_complex") + 1])(
            cd.clip_command("ffmpeg", [], item, "s.mp4", "a.png", None, "o.mp4", cfg))
        self.assertNotIn("fade=t=in:st=0:d=0.150", graph)         # continues the previous clip: no picture fade in
        self.assertIn("afade=t=in:d=0.030", graph)                # only the click guard
        self.assertIn("fade=t=out:st=9.850:d=0.150", graph)
        self.assertIn("afade=t=out:st=9.800:d=0.200", graph)

    def test_fade_is_applied_to_picture_before_the_scoreboard_overlay(self):
        cfg = CondensedConfig()
        item = cd.RenderItem(0, 5.0, 15.0, 1, (0, 0))
        graph = (lambda c: c[c.index("-filter_complex") + 1])(
            cd.clip_command("ffmpeg", [], item, "s.mp4", "a.png", None, "o.mp4", cfg))
        self.assertLess(graph.index("fade=t=out"), graph.index("overlay=0:0"))   # HUD stays solid

    def test_no_fade_gives_hard_cut_with_click_guard_only(self):
        cfg = CondensedConfig(join_video_fade_sec=0.0, join_audio_fade_sec=0.0)
        item = cd.RenderItem(0, 5.0, 15.0, 1, (0, 0))
        graph = (lambda c: c[c.index("-filter_complex") + 1])(
            cd.clip_command("ffmpeg", [], item, "s.mp4", "a.png", None, "o.mp4", cfg))
        self.assertNotIn("fade=t=in:st=0", graph)
        self.assertIn("afade=t=out:st=9.970:d=0.030", graph)

    def test_short_clip_fade_is_capped(self):
        cfg = CondensedConfig()
        item = cd.RenderItem(0, 5.0, 6.0, 1, (0, 0))       # 1 s clip: fade <= d/4
        graph = (lambda c: c[c.index("-filter_complex") + 1])(
            cd.clip_command("ffmpeg", [], item, "s.mp4", "a.png", None, "o.mp4", cfg))
        self.assertIn("fade=t=in:st=0:d=0.150", graph)
        self.assertIn("afade=t=in:d=0.200", graph)

    def test_constant_score_clip_has_single_overlay(self):
        cfg = CondensedConfig()
        item = cd.RenderItem(0, 5.0, 12.0, 1, (2, 1))
        cmd = cd.clip_command("ffmpeg", [], item, "s.mp4", "a.png", None, "o.mp4", cfg)
        self.assertEqual(cmd.count("-i"), 2)

    def test_chapters(self):
        items = [cd.RenderItem(0, 0, 70, 1, (0, 0)), cd.RenderItem(0, 0, 50, 1, (0, 0), (1, 0), 3.0),
                 cd.RenderItem(0, 0, 30, 2, (1, 0), (1, 1), 2.0)]
        text = cd.build_chapters(items, "A", "B")
        self.assertEqual(text.splitlines(), ["0:00 Ván 1: A 1 - 0 B", "2:00 Ván 2: A 1 - 1 B"])

    def test_chapters_with_intro_and_outro(self):
        items = [cd.RenderItem(0, 0, 70, 1, (0, 0)), cd.RenderItem(0, 0, 50, 1, (0, 0), (1, 0), 3.0),
                 cd.RenderItem(0, 0, 30, 2, (1, 0), (1, 1), 2.0)]
        text = cd.build_chapters(items, "A", "B", intro_sec=4.0, outro_sec=6.0, separate_cards=True)
        self.assertEqual(text.splitlines(), ["0:00 Intro", "0:04 Ván 1: A 1 - 0 B", "2:04 Ván 2: A 1 - 1 B",
                                             "2:34 Kết quả"])
        # intro only / outro only
        self.assertEqual(cd.build_chapters(items, "A", "B", intro_sec=4.0, separate_cards=True).splitlines()[-1],
                         "2:04 Ván 2: A 1 - 1 B")
        merged = cd.build_chapters(items, "A", "B", intro_sec=4.0, outro_sec=6.0).splitlines()
        self.assertEqual(merged, ["0:00 Ván 1: A 1 - 0 B", "2:04 Ván 2: A 1 - 1 B"])   # cards folded into rack chapters
        self.assertEqual(cd.build_chapters(items, "A", "B", outro_sec=6.0).splitlines()[0], "0:00 Ván 1: A 1 - 0 B")

    def test_final_result_uses_last_included_rack(self):
        racks = [{"include": True, "winner": 1, "score_after": [1, 0]},
                 {"include": True, "winner": 2, "score_after": [1, 1]},
                 {"include": False, "winner": None}]
        self.assertEqual(cd.final_result(racks), (1, 1, 2))
        self.assertIsNone(cd.final_result([{"include": False}]))

    def test_card_seconds(self):
        self.assertEqual(cd._card_sec(False, None, 4.0), 4.0)
        self.assertEqual(cd._card_sec(False, 2.5, 4.0), 2.5)
        self.assertEqual(cd._card_sec(False, 0, 4.0), 0.0)
        self.assertEqual(cd._card_sec(True, 9.0, 4.0), 0.0)

    def test_render_subcommand_accepts_intro_outro_flags(self):
        from unittest import mock
        with mock.patch.object(cd, "cmd_render") as fake:
            # main() binds fn at parse time from the module attribute, so patch before building the parser
            cd.main(["render", "--project", "x", "--no-intro", "--no-outro", "--intro-sec", "3", "--outro-sec", "5",
                     "--venue", "CLB Test"])
        args = fake.call_args[0][0]
        self.assertTrue(args.no_intro and args.no_outro)
        self.assertEqual((args.intro_sec, args.outro_sec, args.venue), (3.0, 5.0, "CLB Test"))
        with mock.patch.object(cd, "cmd_render") as fake:
            cd.main(["render", "--project", "x"])
        args = fake.call_args[0][0]
        self.assertFalse(args.no_intro or args.no_outro)
        self.assertIsNone(args.intro_sec)
        self.assertIsNone(args.venue)


if __name__ == "__main__":
    unittest.main()
