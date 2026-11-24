import json
import os
import sys
import argparse
from pathlib import Path

from common.rails_context import RailsContext, railway


class ConfigReader:

	def __init__(self):
		self.toc_depth = 0


	#----------------------------------------------
	@railway
	def load_config(self, context: RailsContext):
		return self._read_command_line(context)

	#----------------------------------------------
	@railway
	def _read_command_line(self, context: RailsContext):
		parser = argparse.ArgumentParser(
			prog="python md2html",
			description=(
				"Convert multiple Markdown files into a single HTML file, "
				"copying images to an output folder and rendering mermaid "
				"diagrams to 1280px-wide PNG files."
			),
		)
		parser.add_argument(
			"input_files",
			nargs="+",
			metavar="FILE",
			help="Input Markdown files to convert.",
		)
		parser.add_argument(
			"-o", "--output",
			default="output.html",
			help="Output HTML file path (default: output.html).",
		)
		parser.add_argument(
			"-d", "--output-dir",
			default=None,
			help=(
				"Directory for assets (images/ and mermaid/). "
				"Defaults to the directory containing the output file."
			),
		)
		parser.add_argument(
			"--title",
			default=None,
			help="Title for the output HTML file.",
		)
		parser.add_argument(
			"--no-mermaid-png",
			action="store_true",
			help=(
				"Skip mermaid PNG rendering; rely on browser-side mermaid.js "
				"rendering only."
			),
		)
		parser.add_argument(
			"--no-toc",
			action="store_true",
			help="Skip generating a Table of Contents.",
		)
		parser.add_argument(
			"--toc-depth",
			type=int,
			default=3,
			metavar="N",
			help="Maximum heading depth for TOC (default: 3).",
		)

		settings = parser.parse_args(sys.argv[1:])

		self.title = settings.title
		self.no_png = settings.no_mermaid_png
		self.toc_depth = 0
		if not settings.no_toc:
			self.toc_depth = settings.toc_depth

		self.input_files: list[Path] = [Path(f).resolve() for f in settings.input_files]
		self.output_file = Path(settings.output).resolve()
		self.output_path = (
			Path(settings.output_dir).resolve()
			if settings.output_dir
			else self.output_file.parent
		)

		if not self.input_files:
			return context.setError(False, f"Missing input files")
		return True

	#----------------------------------------------
	@railway
	def _read_environment(self, context: RailsContext):
		return False

	#----------------------------------------------
	@railway
	def _print_settings(self, context: RailsContext):
		print(f"Input: {self.input_files}")
		print(f"Output: {self.output_file}")
		print(f"Output Path: {self.output_path}")
		print(f"Title: {self.title}")
		print(f"No mermaid: {self.no_png}")
		print(f"TOC depth: {self.toc_depth}")
		return False

	#----------------------------------------------
	@railway
	def _read_config_file(self, context: RailsContext, cmd):
		self.settings = {}
		fname = f".config.json"
		try:
			if not os.path.isfile(fname): return { "cmd": cmd }
			with open(fname, 'r') as f:
				self.settings = json.load(f)
				self.settings['cmd'] = cmd
				return self.settings
		except Exception as e:
			return context.setError(False, f"Error reading config file: {e}")


