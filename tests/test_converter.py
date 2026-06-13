import unittest
from pathlib import Path

from app.main import build_ffmpeg_args, sanitize_stem


class ConverterCommandTests(unittest.TestCase):
    def test_blur_command_uses_filter_complex_and_safe_arg_list(self):
        args = build_ffmpeg_args(Path("input.mp4"), Path("output.mp4"), "blur", 18)
        command = " ".join(args)

        self.assertIsInstance(args, list)
        self.assertIn("-filter_complex", args)
        self.assertIn("[0:v]split=2", command)
        self.assertIn("reset_sar=1", command)
        self.assertIn("-map", args)
        self.assertIn("[v]", args)
        self.assertIn("+faststart", args)

    def test_crop_command_outputs_h264_aac_faststart(self):
        args = build_ffmpeg_args(Path("input.mov"), Path("output.mp4"), "crop", 18)
        command = " ".join(args)

        self.assertIn("-vf", args)
        self.assertIn("scale=1080:1920:force_original_aspect_ratio=increase:force_divisible_by=2:reset_sar=1", command)
        self.assertIn("crop=1080:1920", command)
        self.assertIn("libx264", args)
        self.assertIn("aac", args)
        self.assertIn("+faststart", args)

    def test_fit_command_uses_padding_without_stretching(self):
        args = build_ffmpeg_args(Path("input.webm"), Path("output.mp4"), "fit", 24)
        command = " ".join(args)

        self.assertIn("scale=1080:1920:force_original_aspect_ratio=decrease:force_divisible_by=2:reset_sar=1,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black,setsar=1", command)

    def test_output_name_stem_is_sanitized(self):
        self.assertEqual(sanitize_stem("My Clip!.mp4"), "my-clip")
        self.assertEqual(sanitize_stem("...."), "converted-video")


if __name__ == "__main__":
    unittest.main()
