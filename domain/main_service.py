import re
import shutil
from pathlib import Path
import html


import cairosvg
import mermaidx


import markdown
from common.rails_context import RailsContext, railway
from domain.config_reader import ConfigReader

class MainService:

	def __init__(self):
		self.title = "Paper Name"

	#----------------------------------------------
	@railway
	def execute(self, context: RailsContext, settings: ConfigReader):
		self._read_settings(context, settings)
		if not self.input_files: return False

		self.all_image_mapping = {}
		self.sections = []

		for file_index, md_file in enumerate(self.input_files):
			self._parse_markdown(context, file_index, md_file, settings.no_png)

		html = self._generate_html(context, settings.output_path,	toc_depth=settings.toc_depth)
		self._save_html(context, html)
		return self._print_summary(context, settings)

	#region Settings
	#----------------------------------------------
	@railway
	def _read_settings(self, context: RailsContext, settings: ConfigReader):
		self.output_path = settings.output_path
		self.output_file = settings.output_file
		self.input_files = self._verify_input_files(context, settings)
		self.title = self._get_title(context, settings)
		self.mermaid_dir = mermaid_dir = self.output_path / "mermaid"
		self.images_dir = mermaid_dir = self.output_path / "images"

	#----------------------------------------------
	@railway
	def _verify_input_files(self, context: RailsContext, settings: ConfigReader):
		for f in settings.input_files:
			if not f.is_file():
				return context.setError(False, f"ERROR: File not found: {f}")
		return settings.input_files

	#----------------------------------------------
	@railway
	def _get_title(self, context: RailsContext, settings: ConfigReader):
		if settings.title:
			return settings.title
		else:
			stems = [f.stem for f in settings.input_files]
			return " - ".join(stems) if len(stems) > 1 else stems[0]

	#----------------------------------------------
	@railway
	def _print_summary(self, context: RailsContext, settings: ConfigReader):
		print(f"Output file: {self.output_file}")
		print("Images:")
		for img in self.all_image_mapping:
			print(f" - {img}")


	#endregion

	#region Markdown
	#----------------------------------------------
	@railway
	def _parse_markdown(self, context: RailsContext, idx: int, fpath: Path, no_mermaid_png: bool):
		print(f"  : {fpath}")
		md_text = fpath.read_text(encoding="utf-8")
		source_base = fpath.parent
		images, mermaid_blocks = self._extract_images_and_mermaid(context, md_text)

		local_paths = self._collect_local_image_paths(context, md_text)
		image_mapping = self._copy_images(context, source_base, local_paths)
		self.all_image_mapping.update(image_mapping)

		mermaid_replacements: dict[int, str] = {}
		if mermaid_blocks:
			self.mermaid_dir.mkdir(parents=True, exist_ok=True)
			for mermaid_idx, block_source in enumerate(mermaid_blocks):
				block_num = idx * 1000 + mermaid_idx
				img_name = self._render_mermaid(context, block_source, block_num, no_mermaid_png)
				replacement = self._mermaid_block(context, block_source, block_num, img_name)
				mermaid_replacements[block_num] = replacement

		section_html = self._parse_markdown_to_html(context, md_text, mermaid_blocks, mermaid_replacements)
		section_html = self._replace_images_in_html(context, section_html, image_mapping)
		self.sections.append((fpath.stem, section_html))

	#----------------------------------------------
	@railway
	def _extract_images_and_mermaid(self, context: RailsContext, md_text):
		images = []
		mermaid_blocks = []
		for match in re.finditer(r"```mermaid\s*\n(.*?)```", md_text, re.DOTALL):
			mermaid_blocks.append(match.group(1))

		no_mermaid = re.sub(r"```mermaid\s*\n.*?```", "", md_text, flags=re.DOTALL)

		for match in re.finditer(r"!\[([^\]]*)\]\(([^)]+)\)", no_mermaid):
			item = {
				"alt": match.group(1),
				"src": match.group(2)
			}
			images.append(item)
		return images, mermaid_blocks

	#----------------------------------------------
	@railway
	def _copy_images(self, context: RailsContext, source_base, local_paths) -> dict[str, str]:
		mapping: dict[str, str] = {}
		self.images_dir.mkdir(parents=True, exist_ok=True)

		for rel_path in local_paths:
			full_path = source_base / rel_path
			if full_path.is_file():
				filename = Path(full_path.name)
				counter = 1
				dest_name = filename.name
				dest_file = self.images_dir / dest_name
				while dest_file.exists():
					stem = filename.stem
					ext = filename.suffix
					dest_name = f"{stem}_{counter}{ext}"
					dest_file = self.images_dir / dest_name
					counter += 1
				shutil.copy2(str(full_path), str(dest_file))
				mapping[rel_path] = f"{self.images_dir.name}/{dest_name}"

		return mapping

	#----------------------------------------------
	@railway
	def _collect_local_image_paths(self, context: RailsContext, md_text) -> list[str]:
		paths: list[str] = []
		for match in re.finditer(r"!\[([^\]]*)\]\(([^)]+)\)", md_text):
			src = match.group(2)
			if src and not src.startswith(("http://", "https://", "data:", "#")):
				paths.append(src)
		return paths

	#----------------------------------------------
	@railway
	def _parse_markdown_to_html(self, context: RailsContext,  md_text, mermaid_blocks, mermaid_replacements: dict[int, str]) -> str:
		section_html = markdown.markdown(
			md_text,
			extensions=[
				"markdown.extensions.tables",
				"markdown.extensions.fenced_code",
				"markdown.extensions.codehilite",
			],
		)

		pattern = r'<pre class="codehilite">\s*<code class="language-mermaid">\s*(.*?)\s*</code></pre>'
		replacements = sorted(mermaid_replacements.items())
		current = 0

		def replacer(m: re.Match) -> str:
			nonlocal current
			if current < len(replacements):
				block_num, replacement = replacements[current]
				current += 1
				return replacement
			return m.group(0)  # keep original if no replacement

		section_html = re.sub(pattern, replacer, section_html, flags=re.DOTALL)

		return section_html

	#----------------------------------------------
	@railway
	def _replace_images_in_html(self, context: RailsContext,  html_text: str, image_mapping: dict[str, str]) -> str:
		for old_src, new_src in image_mapping.items():
			html_text = html_text.replace(f'src="{old_src}"', f'src="{new_src}"')
			html_text = html_text.replace(f'src=\'{old_src}\'', f'src=\'{new_src}\'', 1)
		return html_text

	#endregion

	#region Diagrams
	#----------------------------------------------
	@railway
	def _render_mermaid(self, context: RailsContext, mermaid_source: str, index: int, no_png: bool) -> str:

		svg_filename = f"mermaid_{index}.svg"
		self._mermaid_to_svg(context, mermaid_source, svg_filename)
		if no_png: return svg_filename

		png_filename = f"mermaid_{index}.png"
		self._svg_to_png(context, svg_filename, png_filename, 1280)
		return png_filename

	#----------------------------------------------
	@railway
	def _mermaid_block(self, context: RailsContext, mermaid_source: str, index: int, img_name: str):
		safe_source = html.escape(mermaid_source)
		if not img_name: return self._mermaid_html(safe_source)
		return self._png_html(f"mermaid/{img_name}", f"Mermaid diagram {index}", safe_source)

	#----------------------------------------------
	@railway
	def _mermaid_to_svg(self, context: RailsContext, mermaid: str, filename: str):
		diagram = mermaidx.render(mermaid)
		svg_code = diagram.svg()
		svg_file = self.mermaid_dir / filename
		with open(svg_file, 'w') as f: f.write(svg_code)
		return True

	#----------------------------------------------
	@railway
	def _svg_to_png(self, context: RailsContext, svg_filename: str, png_filename: str, custom_dpi: int):
		svg_path = self.mermaid_dir / svg_filename
		png_path = self.mermaid_dir / png_filename

		cairosvg.svg2png(url=str(svg_path), write_to=str(png_path), dpi=custom_dpi)
		svg_path.unlink(missing_ok=True)
		return True

	#----------------------------------------------
	def _mermaid_html(self, mcode: str):
		return (
				f'<div class="md2html-mermaid">'
				f'<pre class="mermaid">{mcode}</pre>'
				f'</div>'
		)

	#----------------------------------------------
	def _png_html(self, src: str, alt: str, mcode: str):
		return (
			f'<div class="md2html-mermaid">'
			f'<img src="{src}" alt="{alt}">'
			f'<pre class="mermaid" style="display:none">{mcode}</pre>'
			f'</div>'
		)

	#endregion

	#region HTML

	#----------------------------------------------
	@railway
	def _generate_html(self, context: RailsContext, path, toc_depth) -> str:
		self.output_path.mkdir(parents=True, exist_ok=True)
		htext: list[str] = []

		safe_title = html.escape(self.title)
		self._add_html_head(context, htext, safe_title, 'Desc', 'markdown, mermaid', 'https://cgi.com', '')

		htext.append("<body>")
		self._add_html_toc(context, htext, safe_title, toc_depth)

		for i, (section_title, section_html) in enumerate(self.sections):
			safe_id = re.sub(r"[^a-zA-Z0-9]+", "-", section_title).lower().strip("-")
			if i > 0:
				htext.append('<hr class="file-separator">')
			htext.append(
				f'<div id="section-{safe_id}">{section_html}</div>'
			)

		htext.append("</body>")
		htext.append("</html>")

		return "\n".join(htext)

	#----------------------------------------------
	@railway
	def _save_html(self, context: RailsContext, htext: str):
		self.output_file.parent.mkdir(parents=True, exist_ok=True)
		self.output_file.write_text(htext, encoding="utf-8")
		return True

	#----------------------------------------------
	@railway
	def _add_html_head(self, context: RailsContext, htext, title, description, keywords, url, image):
		htext.append("<!DOCTYPE html>")
		htext.append('<html lang="en">')
		htext.append("<head>")
		htext.append('<meta charset="UTF-8">')
		htext.append('<meta name="viewport" content="width=device-width, initial-scale=1.0">')
		htext.append(f"<title>{title}</title>")
		htext.append(f'<meta name="description" content="{description}">')
		htext.append(f'<meta name="keywords" content="{keywords}">')
		htext.append(f'<meta property="og:title" content="{title}">')
		htext.append(f'<meta property="og:url" content="{url}">')
		htext.append(f'<meta property="og:description" content="A classless CSS framework to write modern websites using only HTML.">')
		htext.append(f'<meta property="og:type" content="article">')
		htext.append(f'<meta property="og:image" content="{image}">')
		htext.append(f'<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/open-fonts@1.1.1/fonts/inter.min.css">')
		htext.append(f'<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@exampledev/new.css@1.1.2/new.min.css">')
		htext.append(f'')
		htext.append(
			'<script src="https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"></script>'
		)
		htext.append(
			'<script>mermaid.initialize({startOnLoad:true,theme:"default"})</script>'
		)
		htext.append("</head>")
		return True

	#----------------------------------------------
	@railway
	def _add_html_toc(self, context: RailsContext, htext, title, toc_depth: int):
		htext.append(f'<header>')
		htext.append(f'<h1>{title}</h1>')
		if toc_depth == 0:
			htext.append(f'</header>')
			return True

		htext.append(f'<nav>')
		menu = []
		for section_title, _ in self.sections:
			safe_id = re.sub(
				r"[^a-zA-Z0-9]+", "-", section_title
			).lower().strip("-")
			menu.append(f'<a href="#section-{safe_id}">{html.escape(section_title)}</a>')
		htext.append(" | ".join(menu))
		htext.append(f'</nav>')
		htext.append(f'</header>')
		return True

	#endregion

	EOF = True