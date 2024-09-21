#!/usr/bin/env python
# -*-coding:utf-8 -*-
import os
import re
import traceback
import warnings

import flet
from ebooklib import epub
from flet import (
    Page,
)
from lxml import etree

from check import version_check, GITHUB_URL

warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

coding = 'utf-8'
parser = etree.XMLParser(ns_clean=True, recover=True, encoding=coding)

"""
EPUB 文件格式是一种专为电子书设计的标准格式，它允许文本和其他内容根据设备屏幕的大小自动调整。EPUB 文件实际上是 ZIP 格式的文件，包含了 HTML 文档、图像、CSS 样式表以及其他支持文件。以下是 EPUB 文件的基本结构和组成部分：

Mimetype 文件：位于 EPUB 包的根目录下，是一个纯文本文件，包含值 application/epub+zip。此文件没有文件扩展名，并且必须是未压缩的（即不在 ZIP 压缩之内），这是 EPUB 阅读器识别 EPUB 文件的第一步。
META-INF 目录：
    container.xml：描述了 EPUB 文件内部其他 XML 文件的位置。它指定了 OPS（或 OEBPS）目录的位置，这是 EPUB 文件的主要内容所在的位置。
OPS 或 OEBPS 目录：这是 EPUB 文件的主要部分，包含了电子书的所有内容。此目录包括：
    content.opf：这是一个 XML 文件，定义了整个 EPUB 包的内容。它包含了元数据、内容清单（manifest）、排版顺序（spine）和导航指南（guide）等信息。
    toc.ncx：一个 XML 文件，定义了书的目录结构。虽然在 EPUB 3 中已经被 XHTML 导航文件取代，但在某些阅读器中仍然会被使用。
    nav.xhtml：一个 XHTML 文件，作为电子书的导航文档。在 EPUB 3 中代替了 toc.ncx 文件。
    Text 目录：包含了电子书的所有正文内容，这些内容是以 XHTML 文件的形式存在的。
    Images 目录：存放电子书中使用的图像文件。
    Styles 目录：存放用于格式化内容的 CSS 文件。
Cover 图像：有些 EPUB 文件会包含封面图像，通常作为一个独立的图像文件存在于 Images 目录中，并在 content.opf 文件中引用。
"""


class UI:

    def __init__(self, page: flet.Page):
        self.page = page
        self.input_files = flet.ListView(
            spacing=10, padding=10, height=400
        )
        output_file = os.path.abspath('合并.epub')
        self.count = flet.Text(weight=flet.FontWeight.BOLD)

        self.pick_files_dialog = flet.FilePicker(on_result=self.pick_files_result)
        self.pb = flet.ProgressBar(width=600, tooltip="合并进度", value=0)
        self.pb_label = flet.Text("0.00%")

        page.overlay.append(self.pick_files_dialog)

        self.merge_b = flet.ElevatedButton(
            "开始合并",
            icon=flet.icons.MERGE,
            on_click=lambda _: self.handle([i.value for i in self.input_files.controls], output_file),  # type: ignore
        )

        page.add(
            flet.Column(
                [
                    flet.Row([
                        flet.ElevatedButton(
                            "选择多个epub",
                            icon=flet.icons.SELECT_ALL,
                            on_click=lambda _: self.pick_files_dialog.pick_files(
                                allow_multiple=True
                            ),
                        ),
                        flet.ElevatedButton(text="项目主页", url=GITHUB_URL)
                    ]),

                    self.input_files,
                    self.count,
                    self.merge_b,
                    flet.Row(controls=[self.pb, self.pb_label]),

                ]
            )
        )

    def handle(self, epubs, output_name):
        if not epubs:
            return
        self.merge_b.disabled = True
        merged_epub = epub.EpubBook()
        first_book = epub.read_epub(epubs[0])
        print(first_book.metadata)
        try:
            merged_epub.set_identifier(first_book.get_metadata('DC', 'identifier')[0][0])
            merged_epub.set_title(first_book.get_metadata('DC', 'title')[0][0])
            merged_epub.set_language(first_book.get_metadata('DC', 'language')[0][0])
            merged_epub.add_author(first_book.get_metadata('DC', 'creator')[0][0])
        except Exception as e:
            print("error:", e)

        dirs = [r'.*nav.xhtml', r'.*contents.xhtml', r'.*toc.xhtml', r'.*toc.ncx']
        dirs_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in dirs]

        self.update_pb(0.1)
        self.merge_b.text = "合并中..."
        self.page.update()

        one = 0.85 / len(epubs)
        for i, epub_file in enumerate(epubs):
            try:
                self.files_conbine(i, epub_file, dirs_patterns, merged_epub)
            except Exception as e:
                print(e)
            self.update_pb(self.pb.value + one)

        self.merge_b.text = "合并完成，导出中..."
        self.merge_b.update()

        nav = epub.EpubNav()
        nav.file_name = "Text/toc.xhtml"
        # merged_epub.add_item(epub.EpubNcx()) #EPUB2规范
        merged_epub.add_item(nav)  # EPUB3规范
        epub.write_epub(output_name, merged_epub)
        self.update_pb(self.pb.value + 0.05)
        self.merge_b.disabled = False
        self.merge_b.text = "开始合并"

        self.count.value = f"已导出到 {output_name}"
        self.page.update()

    def update_pb(self, i):
        self.pb.value = i
        self.pb_label.value = f"{self.pb.value * 100:.2f}%"
        self.page.update()

    def pick_files_result(self, e: flet.FilePickerResultEvent):
        if not e.files:
            return
        self.input_files.controls.clear()
        self.input_files.controls.extend([flet.Text(i.path) for i in e.files])
        self.count.value = f"累计{len(self.input_files.controls)}个文件"
        e.page.update()

    # 查找章节位置
    # 通过遍历章节列表，查找包含指定位置的章节
    # 如果找不到，则返回原始位置
    def findloc(self, charpters, loc):
        for charpter in charpters:
            if loc in charpter:
                return charpter
        return loc

    def addtoc(self, item, chapters, toc):
        lxml_content = item.get_content()
        tree = etree.fromstring(lxml_content, parser)
        title_elements = tree.findall('.//{http://www.w3.org/1999/xhtml}a')
        for title_element in title_elements:
            href = title_element.get('href')
            loc = os.path.basename(href)
            loc = self.findloc(chapters, loc)
            title_name = ''.join(title_element.itertext())
            loc = os.path.join("Text", loc).replace(os.path.sep, '/')
            link = epub.Link(loc, title_name, item.id)
            same = False
            for t in toc:
                if t.href == link.href:
                    same = True
                    break

            if not same:
                yield link
        return None

    def modify_img(self, item, chapters):

        lxml_content = item.content
        tree = etree.fromstring(lxml_content, parser=parser)
        imgs = tree.findall('.//{http://www.w3.org/1999/xhtml}img')

        namespaces = {'xlink': 'http://www.w3.org/1999/xlink', 'svg': 'http://www.w3.org/2000/svg'}
        # 查找所有 <image> 元素
        images = tree.xpath('.//svg:image', namespaces=namespaces)

        for img in imgs:
            src = img.get('src')
            loc = os.path.basename(src)
            for chapter in chapters:
                if loc in chapter:
                    img.set('src', os.path.join(os.path.dirname(src), chapter).replace(os.path.sep, '/'))
                    break
        for image in images:
            href = image.get('{http://www.w3.org/1999/xlink}href')
            loc = os.path.basename(href)
            for chapter in chapters:
                if loc in chapter:
                    image.set('{http://www.w3.org/1999/xlink}href',
                              os.path.join(os.path.dirname(href), chapter).replace(os.path.sep, '/'))
        return etree.tostring(tree, pretty_print=True, encoding=coding, xml_declaration=True).decode(coding)

    def files_conbine(self, i, epub_file, dirs_patterns, merged_epub):

        book = epub.read_epub(epub_file)
        chapters, toc, spine = [], [], ['nav']
        for item in book.items:
            basename = os.path.basename(item.file_name)
            afterDeclaration = basename[basename.rindex('.'):]
            item.id = f"{i}_{basename}"
            if afterDeclaration not in item.id:
                item.id += afterDeclaration

            item.file_name = os.path.join(os.path.dirname(item.file_name), str(i) + "_" + basename).replace(
                os.path.sep,
                '/')
            chapters.append(item.id)

        for item in book.items:
            f = False
            for pattern in dirs_patterns:
                if pattern.search(item.id):
                    f = True
                    add_contents = self.addtoc(item, chapters, toc)
                    if add_contents is not None:
                        toc.extend(add_contents)
            if not f:
                if ".xhtml" in item.id:
                    modify_content = self.modify_img(item, chapters)
                    item.set_content(modify_content.encode(coding))
                merged_epub.add_item(item)
        # set spine
        for t in toc:
            # print(t.href)
            for item in book.items:
                if item.id in t.href:
                    spine.append(item.id)
        merged_epub.toc.extend(toc)
        merged_epub.spine.extend(spine)

    def get_files(self, directory):
        # 使用示例
        _files = []
        for root, dirs, files in os.walk(directory):
            for file in files:
                _files.append(os.path.abspath(os.path.join(root, file)))
        return _files


def main(page: Page):
    page.title = "epub合并工具（bronya0制作）"
    page.theme = flet.Theme(font_family="微软雅黑")

    UI(page)

    try:
        version_check(page)
    except:
        traceback.print_exc()


flet.app(target=main)
