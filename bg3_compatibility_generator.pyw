#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BG3 MOD兼容性工具
批量处理种族和外观mod，生成兼容补丁
"""

import os
import sys
import re
import uuid
import json
import shutil
import subprocess
import tempfile
import zipfile
import hashlib
import threading
import queue
import webbrowser
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import tkinter as tk

# 种族UUID映射
from src.race_uuid_mapping import VANILLA_RACE_MAPPING, is_vanilla_race, get_race_options

def get_application_path():
    """获取程序路径，支持开发和打包环境"""
    if getattr(sys, 'frozen', False):
        # 打包exe
        return Path(sys.executable).parent
    else:
        # 开发模式
        return Path(__file__).parent

# 导入UI模块
from src.ui import PatchInfoDialog, UIManager

try:
    import tkinter as tk
    from tkinter import messagebox
except ImportError:
    print("错误：无法导入tkinter。请确保Python安装包含tkinter模块。")
    sys.exit(1)



class BG3CompatibilityGenerator:
    def __init__(self):
        self.root = tk.Tk()
        
        # 获取程序路径
        self.app_dir = get_application_path()
        
        # 本地化初始化
        self.current_language = "zh_CN"  # 默认中文
        self.texts = {}
        self.load_language(self.current_language)
        
        self.root.title(self.texts.get("window_title", "博德之门3 MOD兼容性自动生成工具"))
        self.root.geometry("1000x700")
        self.root.resizable(True, True)
        
        # 先隐藏窗口
        self.root.withdraw()
        
        # 工具路径
        self.divine_exe = self.app_dir / "Data" / "Tools" / "Divine" / "Divine.exe"
        self.temp_dir = Path(tempfile.gettempdir()) / "bg3_compatibility_temp"
        
        # 数据目录
        self.data_dir = self.app_dir / "Data"
        self.sourcemod_dir = self.data_dir / "Sourcemod"
        self.panagway_dir = self.data_dir / "Panagway"
        self.output_dir = self.data_dir / "Output"
        
        # 数据存储
        self.selected_race_paks = []
        self.selected_appearance_paks = []
        self.race_data = {}  # 种族数据
        self.appearance_data = {}  # 外观数据
        
        # 外观MOD种族选择
        self.appearance_race_selections = {}  # {pak_file_path: selected_race_uuid}
        self.appearance_race_widgets = {}  # {pak_file_path: {"frame": frame, "combobox": combobox}}
        self.appearance_vanilla_races = {}  # {pak_file_path: [vanilla_race_uuids]}
        
        # 固定UUID
        self.fixed_uuid = None
        
        # 异步任务
        self.task_queue = queue.Queue()
        self.current_task_thread = None
        self.is_task_running = False
        
        # 创建UI管理器
        self.ui_manager = UIManager(self)
        
        # 创建界面
        self.ui_manager.create_widgets()
        
        # 确保目录存在
        self.ensure_directories()
        
        # 自动加载pak文件
        self.auto_load_preset_paks()
        
        # 显示窗口并居中
        self.center_window()
        
        # 设置窗口图标
        if getattr(sys, 'frozen', False):
            # 打包环境 - 图标在_MEIPASS的src/asset/image目录下
            icon_path = Path(sys._MEIPASS) / "src" / "asset" / "image" / "打包图标.ico"
        else:
            # 开发环境
            icon_path = self.app_dir / "src" / "asset" / "image" / "打包图标.ico"
        
        if icon_path.exists():
            try:
                self.root.iconbitmap(str(icon_path))
                print(f"✓ 图标加载成功: {icon_path}")
            except Exception as e:
                print(f"✗ 图标加载失败: {e}")
        else:
            print(f"✗ 图标文件不存在: {icon_path}")
        
        self.root.deiconify()
        
        # 启动任务队列
        self.process_task_queue()
    
    def get_application_path(self):
        """获取程序路径，支持开发和打包环境"""
        if getattr(sys, 'frozen', False):
            # 打包后的环境
            return Path(sys.executable).parent
        else:
            # 开发环境
            return Path(__file__).parent
    
    def process_task_queue(self):
        """处理任务队列消息"""
        try:
            while True:
                message = self.task_queue.get_nowait()
                if message['type'] == 'progress':
                    self.progress_bar['value'] = message['value']
                    self.progress_var.set(message['text'])
                elif message['type'] == 'complete':
                    self.is_task_running = False
                    self.progress_bar['value'] = 100
                    self.progress_var.set(message['text'])
                    # 生成完成后打开输出目录
                    if message.get('subtype') == 'generate_patch':
                        self.open_output_directory()
                elif message['type'] == 'error':
                    # 错误消息
                    self.progress_bar['value'] = 0
                    self.progress_var.set(self.texts.get("progress_idle", "就绪"))
                    self.ui_manager.show_error_message(self.texts.get("error_title", "错误"), message['text'])
                elif message['type'] == 'file_progress':
                    # 文件复制进度更新
                    self.progress_bar['value'] = message['value']
                    self.progress_var.set(message['text'])
        except queue.Empty:
            pass
        
        # 每100ms检查队列
        self.root.after(100, self.process_task_queue)
    
    def _import_and_extract_files_async(self, files, dest_dir, file_type):
        """异步导入解包文件"""
        try:
            # 确保目标目录存在
            dest_dir.mkdir(parents=True, exist_ok=True)
            
            total_files = len(files)
            processed_count = 0
            
            for i, file_path in enumerate(files):
                try:
                    source_file = Path(file_path)
                    dest_file = dest_dir / source_file.name
                    
                    # 复制进度
                    progress = (i / total_files) * 50  # 复制占50%进度
                    self.task_queue.put({
                        'type': 'file_progress',
                        'value': progress,
                        'text': self.texts.get("progress_copying_race" if file_type == "种族" else "progress_copying_appearance", f"正在复制{file_type}文件: {{file_name}} ({{current}}/{{total}})").format(file_name=source_file.name, current=i+1, total=total_files)
                    })
                    
                    # 文件存在则跳过复制
                    if not dest_file.exists():
                        shutil.copy2(source_file, dest_file)
                    
                    # 解包进度
                    progress = 50 + (i / total_files) * 50  # 解包占50%进度
                    self.task_queue.put({
                        'type': 'file_progress',
                        'value': progress,
                        'text': self.texts.get("progress_unpacking_race" if file_type == "种族" else "progress_unpacking_appearance", f"正在解包{file_type}文件: {{file_name}} ({{current}}/{{total}})").format(file_name=source_file.name, current=i+1, total=total_files)
                    })
                    
                    # 解包文件
                    pak_type = "race" if file_type == "种族" else "appearance"
                    extract_dir = dest_dir / source_file.stem
                    
                    # 删除旧解包目录
                    if extract_dir.exists():
                        shutil.rmtree(extract_dir)
                    
                    # 解包文件
                    self._extract_pak_to_directory(str(dest_file), extract_dir)
                    processed_count += 1
                    
                except Exception as e:
                    self.task_queue.put({
                        'type': 'error',
                        'text': self.texts.get("progress_copy_failed", "处理文件 {file_name} 失败: {error}").format(file_name=source_file.name, error=str(e))
                    })
                    continue
            
            # 刷新列表
            self.task_queue.put({
                'type': 'complete',
                'subtype': 'import_files',
                'text': self.texts.get("progress_copy_success", "成功处理 {count} 个{file_type}文件").format(count=processed_count, file_type=file_type)
            })
            
            # 主线程刷新pak列表
            self.root.after(0, self.refresh_pak_lists)
            
        except Exception as e:
            self.task_queue.put({
                'type': 'error',
                'text': f"导入{file_type}文件时发生错误: {str(e)}"
            })
    
    def _extract_pak_to_directory(self, pak_file: str, extract_dir: Path):
        """解包pak文件"""
        try:
            # 确保目录存在
            extract_dir.mkdir(parents=True, exist_ok=True)
            
            # 调用Divine.exe解包
            cmd = [
                str(self.divine_exe),
                "--game", "bg3",
                "--action", "extract-package",
                "--source", pak_file,
                "--destination", str(extract_dir)
            ]
            
            # Windows隐藏控制台
            creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.divine_exe.parent, creationflags=creation_flags)
            
            if result.returncode != 0:
                error_msg = result.stderr if result.stderr else result.stdout
                raise Exception(f"Divine.exe解包失败 (返回码: {result.returncode}): {error_msg}")
            
            # 检查解包结果
            if not extract_dir.exists() or not any(extract_dir.iterdir()):
                raise Exception(f"解包后目录为空或不存在: {extract_dir}")
                
        except Exception as e:
            raise Exception(f"解包 {Path(pak_file).name} 失败: {e}")
    
    def load_language(self, language_code):
        """加载语言文件"""
        try:
            # 打包后语言文件位置
            if getattr(sys, 'frozen', False):
                # 打包版
                locale_file = Path(sys._MEIPASS) / "locales" / f"{language_code}.json"
            else:
                # 开发版
                locale_file = self.app_dir / "locales" / f"{language_code}.json"
            if locale_file.exists():
                with open(locale_file, 'r', encoding='utf-8') as f:
                    self.texts = json.load(f)
            else:
                # 使用默认文本
                self.texts = {
                    "window_title": "博德之门3 MOD兼容性自动生成工具",
                    "language_label": "语言:",
                    "select_race_paks": "选择种族pak文件",
            "select_appearance_paks": "选择外观pak文件",
            "delete_file": "删除文件",
            "confirm_delete": "确认删除",
            "confirm_delete_message": "确定要删除文件 {file_name} 吗？",
            "success": "成功",
            "delete_success": "文件 {file_name} 已删除",
            "error": "错误",
            "delete_error": "删除文件时出错: {0}",
            "warning_title": "警告",
            "warning_task_running": "有任务正在运行，请等待完成后再操作",
            "select_race_dialog_title": "选择种族MOD pak文件",
            "select_appearance_dialog_title": "选择外观MOD pak文件",
            "file_types_pak": "PAK文件",
            "file_types_all": "所有文件",
            "progress_copying_race": "正在复制种族文件: {file_name} ({current}/{total})",
            "progress_copying_appearance": "正在复制外观文件: {file_name} ({current}/{total})",
            "progress_copy_failed": "复制文件 {file_name} 失败: {error}",
            "progress_copy_success": "成功复制 {count} 个{file_type}文件",
            "progress_copy_error": "复制{file_type}文件失败: {error}",
            "progress_unpacking_race": "正在解包种族文件: {file_name}",
            "progress_unpacking_appearance": "正在解包外观文件: {file_name}",
            "progress_parsing_data": "正在解析配置数据...",
            "progress_generating_patch": "正在生成兼容性补丁...",
            "progress_packing_mod": "正在打包MOD...",
            "progress_idle": "就绪",
            "error_input_mod_name": "请输入MOD名称",
            "error_input_author": "请输入作者名称",
            "error_input_version": "请输入版本号"
                }
        except Exception as e:
            print(f"加载语言文件失败: {e}")
            self.texts = {}
    
    def change_language(self, language_code):
        """切换语言"""
        self.current_language = language_code
        self.load_language(language_code)
        self.ui_manager.update_ui_texts()
    

    
    def generate_bg3_uuid(self):
        """生成BG3兼容的UUID，使用标准GUID格式"""
        # 生成UUID4格式
        return str(uuid.uuid4()).lower()
    
    def check_existing_meta_file(self):
        """检查是否存在meta.lsx文件并解析其内容"""
        # 动态搜索meta.lsx文件
        meta_path = None
        
        # 在output_dir下搜索所有可能的meta.lsx文件
        import glob
        search_pattern = str(self.output_dir / "*" / "Mods" / "*" / "meta.lsx")
        meta_files = glob.glob(search_pattern)
        
        if meta_files:
            meta_path = Path(meta_files[0])  # 使用找到的第一个meta.lsx文件

        else:

            return {
                'exists': False,
                'mod_name': '',
                'author': '',
                'description': '',
                'version': '',
                'uuid': '',
                'regenerate_uuid': True
            }
        
        if not meta_path.exists():
            # 没有meta文件就返回空

            return {
                'exists': False,
                'mod_name': '',
                'author': '',
                'description': '',
                'version': '',
                'uuid': '',
                'regenerate_uuid': True
            }
        
        try:
            # 解析现有的meta.lsx文件
            import xml.etree.ElementTree as ET
            tree = ET.parse(meta_path)
            root = tree.getroot()
            
            # 提取信息
            mod_name = ''
            author = ''
            description = ''
            version = ''
            uuid_value = ''
            
            # 查找各个字段
            for attribute in root.findall('.//attribute'):
                attr_id = attribute.get('id')
                if attr_id == 'Name':
                    mod_name = attribute.get('value', '')
                elif attr_id == 'Author':
                    author = attribute.get('value', '')
                elif attr_id == 'Description':
                    description = attribute.get('value', '')
                elif attr_id == 'UUID':
                    uuid_value = attribute.get('value', '')
                elif attr_id == 'Version64':
                    # 将Version64转换回版本号格式
                    version64 = int(attribute.get('value', '0'))
                    major = (version64 >> 55) & 0xFF
                    minor = (version64 >> 47) & 0xFF
                    revision = (version64 >> 31) & 0xFFFF
                    build = (version64 >> 16) & 0x7FFF
                    version = f"{major}.{minor}.{revision}.{build}"
            

            return {
                'exists': True,
                'mod_name': mod_name,
                'author': author,
                'description': description,
                'version': version,
                'uuid': uuid_value,
                'regenerate_uuid': False  # 存在文件时不勾选重新生成UUID
            }
            
        except Exception as e:

            # 解析失败时返回空信息
            return {
                'exists': False,
                'mod_name': '',
                'author': '',
                'description': '',
                'version': '',
                'uuid': '',
                'regenerate_uuid': True
            }
    
    def auto_load_preset_paks(self):
        """自动加载预设pak文件"""
        try:

            self.refresh_pak_lists()
        except Exception as e:
            pass
    
    def ensure_directories(self):
        """确保目录存在"""
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.sourcemod_dir.mkdir(parents=True, exist_ok=True)
        self.panagway_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)


    
    def update_race_listbox(self):
        """更新种族列表框"""
        self.ui_manager.update_race_listbox()
    
    def on_appearance_frame_configure(self, event):
        """配置外观滚动框架"""
        self.appearance_canvas.configure(scrollregion=self.appearance_canvas.bbox("all"))
    
    def on_appearance_canvas_configure(self, event):
        """配置外观画布"""
        canvas_width = event.width
        self.appearance_canvas.itemconfig(self.appearance_canvas_window, width=canvas_width)
    
    def update_appearance_listbox(self):
        """更新外观MOD显示区域"""
        self.ui_manager.update_appearance_listbox()
    
    def _set_combobox_default_value(self, combobox, pak_path, race_options):
        """设置Combobox的默认值"""
        try:
            # 设置默认选择（如果之前有选择的话）
            if pak_path in self.appearance_race_selections:
                selected_uuid = self.appearance_race_selections[pak_path]
                for option in race_options:
                    if option[1] == selected_uuid:
                        combobox.set(option[0])
                        break
            else:
                # 默认选择第一个选项
                if race_options:
                    combobox.set(race_options[0][0])
                    self.appearance_race_selections[pak_path] = race_options[0][1]
        except Exception as e:
            # 设置失败就用默认
            if race_options:
                combobox.set(race_options[0][0])
                self.appearance_race_selections[pak_path] = race_options[0][1]
    
    def on_race_selection_changed(self, pak_path, combobox):
        """处理种族选择变化"""
        selected_display_name = combobox.get()
        
        # 根据显示名称找到对应的UUID（使用该MOD特定的种族选项）
        race_options = self.get_mod_race_options(pak_path)
        for option in race_options:
            if option[0] == selected_display_name:
                self.appearance_race_selections[pak_path] = option[1]
                break
    
    def check_appearance_has_vanilla_races(self, pak_path):
        """检查外观MOD是否包含原版种族UUID"""
        try:
            # 检查是否已经检测过并存储了原版种族UUID
            return pak_path in self.appearance_vanilla_races and len(self.appearance_vanilla_races[pak_path]) > 0
        except Exception as e:
            return False
    
    def get_mod_race_options(self, pak_path):
        """获取特定MOD中实际包含的种族选项"""
        try:
            if pak_path in self.appearance_vanilla_races:
                mod_race_uuids = self.appearance_vanilla_races[pak_path]
                options = []
                for uuid in mod_race_uuids:
                    race_info = VANILLA_RACE_MAPPING.get(uuid.lower())
                    if race_info:
                        # 使用本地化名称
                        if 'localization_key' in race_info:
                            display_name = self.texts.get(race_info['localization_key'], race_info['name_zh'])
                        else:
                            # 回退到硬编码格式
                            display_name = f"{race_info['name_zh']} ({race_info['name_en']})"
                        
                        if race_info['subrace']:
                            display_name += f" - {race_info['subrace']}"
                        options.append((display_name, uuid))
                
                # 按显示名称排序
                options.sort(key=lambda x: x[0])
                return options
            else:
                # 没检测到种族就返回空
                return []
        except Exception as e:
            return []
    
    def refresh_appearance_race_comboboxes(self):
        """刷新所有外观种族下拉菜单的文本"""
        try:
            for pak_path, widgets in self.appearance_race_widgets.items():
                combobox = widgets.get('combobox')
                if combobox:
                    # 保存当前选择的UUID
                    current_selection_uuid = self.appearance_race_selections.get(pak_path)
                    
                    # 获取更新后的种族选项
                    race_options = self.get_mod_race_options(pak_path)
                    
                    # 更新下拉菜单的选项
                    combobox['values'] = [option[0] for option in race_options]
                    
                    # 恢复之前的选择
                    if current_selection_uuid:
                        for option in race_options:
                            if option[1] == current_selection_uuid:
                                combobox.set(option[0])
                                break
                    else:
                        # 没有之前选择就用默认
                        if race_options:
                            combobox.set(race_options[0][0])
                            self.appearance_race_selections[pak_path] = race_options[0][1]
        except Exception as e:
            pass  # 忽略异常
    
    def delete_appearance_file_by_path(self, pak_path):
        """通过路径删除外观文件和对应的解包文件夹"""
        try:
            if pak_path in self.selected_appearance_paks:
                pak_file = Path(pak_path)
                file_name = pak_file.name
                
                # 确认删除
                if messagebox.askyesno(self.texts.get("confirm_delete", "确认删除"), 
                                     self.texts.get("confirm_delete_message", f"确定要删除文件 {file_name} 吗？").format(file_name=file_name)):
                    # 从列表中移除
                    self.selected_appearance_paks.remove(pak_path)
                    
                    # 从种族选择中移除
                    if pak_path in self.appearance_race_selections:
                        del self.appearance_race_selections[pak_path]
                    
                    # 从原版种族数据中移除
                    if pak_path in self.appearance_vanilla_races:
                        del self.appearance_vanilla_races[pak_path]
                    
                    # 删除物理文件
                    if pak_file.exists():
                        pak_file.unlink()
                    
                    # 删除对应的解包文件夹
                    extract_dir = self.panagway_dir / pak_file.stem
                    if extract_dir.exists():
                        shutil.rmtree(extract_dir)
                    
                    # 更新显示
                    self.update_appearance_listbox()
                    
                    self.ui_manager.show_info_message(self.texts.get("success", "成功"), 
                                      self.texts.get("delete_success", f"文件 {file_name} 已删除").format(file_name=file_name))
                
        except Exception as e:
            self.ui_manager.show_error_message(self.texts.get("error", "错误"), 
                                self.texts.get("delete_error", "删除文件时出错: {error}").format(error=str(e)))
    
    def refresh_pak_lists(self):
        """刷新pak文件列表"""
        try:
            # 清空当前列表和数据
            self.selected_race_paks.clear()
            self.selected_appearance_paks.clear()
            self.appearance_vanilla_races.clear()
            self.appearance_race_selections.clear()
            
            # 扫描Sourcemod文件夹中的pak文件
            if self.sourcemod_dir.exists():
                for pak_file in self.sourcemod_dir.glob("*.pak"):
                    self.selected_race_paks.append(str(pak_file))
            
            # 扫描Panagway文件夹中的pak文件
            if self.panagway_dir.exists():
                for pak_file in self.panagway_dir.glob("*.pak"):
                    self.selected_appearance_paks.append(str(pak_file))
            
            # 解析外观数据以检测原版种族UUID
            if self.panagway_dir.exists():
                for appearance_subfolder in self.panagway_dir.iterdir():
                    if appearance_subfolder.is_dir():
                        self.parse_appearance_data(appearance_subfolder)
            
            # 更新列表框显示
            self.update_race_listbox()
            self.update_appearance_listbox()
            
            race_count = len(self.selected_race_paks)
            appearance_count = len(self.selected_appearance_paks)
            
            # 在进度条上方显示刷新结果
            message = self.texts.get("refresh_success", "刷新完成！找到 {race_count} 个种族文件，{appearance_count} 个外观文件。").format(
                race_count=race_count, appearance_count=appearance_count
            )
            self.progress_var.set(message)
            
        except Exception as e:
            self.progress_var.set(f"刷新列表时出错：{str(e)}")
    
    def show_race_context_menu(self, event):
        """显示种族列表框右键菜单"""
        self.ui_manager.show_race_context_menu(event)
    
    def show_appearance_context_menu(self, event):
        """显示外观列表框右键菜单"""
        self.ui_manager.show_appearance_context_menu(event)
    
    def delete_race_file(self, index):
        """删除指定索引的种族pak文件和对应的解包文件夹"""
        self.ui_manager.delete_race_file(index)
    
    def delete_appearance_file(self, index):
        """删除指定索引的外观pak文件和对应的解包文件夹"""
        self.ui_manager.delete_appearance_file(index)

    def clear_race_selection(self):
        """清除种族文件夹（删除Sourcemod文件夹内的所有内容）"""
        self.ui_manager.clear_race_selection()
    
    def clear_appearance_selection(self):
        """清除外观文件夹（删除Panagway文件夹内的所有内容）"""
        self.ui_manager.clear_appearance_selection()
    
    def open_output_directory(self):
        """打开输出文件夹"""
        # 创建目录
        if not self.output_dir.exists():
            self.output_dir.mkdir(parents=True, exist_ok=True)
        os.startfile(str(self.output_dir))
    

    

    
    def generate_compatibility(self):
        """生成兼容性补丁"""
        if self.is_task_running:
            self.ui_manager.show_warning_message(self.texts.get("warning_title", "警告"), self.texts.get("warning_task_running", "有任务正在运行，请等待完成后再操作"))
            return
            
        if not self.selected_race_paks:
            self.ui_manager.show_error_message(self.texts.get("error_title", "错误"), self.texts.get("error_no_race_pak", "请至少选择一个种族pak文件"))
            return
        
        if not self.selected_appearance_paks:
            self.ui_manager.show_error_message(self.texts.get("error_title", "错误"), self.texts.get("error_no_appearance_pak", "请至少选择一个外观pak文件"))
            return
        
        if not self.divine_exe.exists():
            self.ui_manager.show_error_message(self.texts.get("error_title", "错误"), self.texts.get("error_divine_not_found", "找不到Divine.exe工具: {path}").format(path=self.divine_exe))
            return
        
        # 检查是否存在meta.lsx文件并预填充信息
        existing_meta_info = self.check_existing_meta_file()
        
        # 弹出补丁信息输入对话框
        dialog = PatchInfoDialog(self, existing_meta_info)
        self.root.wait_window(dialog.dialog)
        
        if dialog.result is None:
            # 用户取消了操作
            return
            
        # 保存用户输入的信息
        self.patch_info = dialog.result
        
        # 启动异步生成任务
        self.is_task_running = True
        self.current_task_thread = threading.Thread(target=self._generate_compatibility_async)
        self.current_task_thread.daemon = True
        self.current_task_thread.start()
    
    def _generate_compatibility_async(self):
        """异步生成补丁"""
        try:
            self.task_queue.put({
                'type': 'progress',
                'value': 0,
                'text': self.texts.get("progress_start_generating", "开始生成兼容性补丁...")
            })
            
            # 3个步骤：解析数据、生成补丁、打包MOD
            total_steps = 3
            current_step = 0
            
            # 解析数据
            self.parse_extracted_data()
            current_step += 1
            progress = (current_step / total_steps) * 100
            self.task_queue.put({
                'type': 'progress',
                'value': progress,
                'text': self.texts.get("progress_parsing_data", "正在解析配置数据...")
            })
            
            # 生成补丁
            self.create_compatibility_patches()
            current_step += 1
            progress = (current_step / total_steps) * 100
            self.task_queue.put({
                'type': 'progress',
                'value': progress,
                'text': self.texts.get("progress_generating_patch", "正在生成兼容性补丁...")
            })
            
            # 打包MOD
            self.pack_mod()
            current_step += 1
            self.task_queue.put({
                'type': 'progress',
                'value': 100,
                'text': self.texts.get("progress_packing_mod", "正在打包MOD...")
            })
            
            # 完成
            self.task_queue.put({
                'type': 'complete',
                'subtype': 'generate_patch',
                'text': self.texts.get("success_generation_complete", "兼容性补丁生成完成！")
            })
            
        except Exception as e:
            self.task_queue.put({
                'type': 'error',
                'text': f"{self.texts.get('error_generation_failed', '生成失败')}: {str(e)}"
            })
            import traceback
            traceback.print_exc()
    

    
    def parse_extracted_data(self):
        """解析数据"""
        # 解析种族数据
        if self.sourcemod_dir.exists():
            for race_subfolder in self.sourcemod_dir.iterdir():
                if race_subfolder.is_dir():
                    self.parse_race_data(race_subfolder)
        
        # 解析外观数据
        if self.panagway_dir.exists():
            for appearance_subfolder in self.panagway_dir.iterdir():
                if appearance_subfolder.is_dir():
                    self.parse_appearance_data(appearance_subfolder)
    
    def parse_race_data(self, race_folder: Path):
        """解析种族数据"""

        
        # 查找Races.lsx文件
        races_files = list(race_folder.rglob("Races.lsx"))
        
        
        if races_files:
            for races_file in races_files:
                pass
        
        race_found = False
        
        # 提取种族UUID
        if races_files:
            for races_file in races_files:
                try:
                    content = races_file.read_text(encoding='utf-8')
                    
                    # 查找种族UUID
                    race_pattern = r'<node id="Race">.*?<attribute id="UUID" type="guid" value="([^"]+)"\s*/>'
                    race_matches = re.findall(race_pattern, content, re.DOTALL)
                    
                    if race_matches:
                        # 使用目录名作为种族名称
                        race_parent_folder = races_file.parent
                        while race_parent_folder != race_folder and race_parent_folder.parent != race_folder:
                            race_parent_folder = race_parent_folder.parent
                        
                        race_name = race_parent_folder.name
                        race_uuid = race_matches[0]
                        
                        # 避免重名
                        original_race_name = race_name
                        counter = 1
                        while race_name in self.race_data:
                            race_name = f"{original_race_name}_{counter}"
                            counter += 1
                        
                        self.race_data[race_name] = {
                            'uuid': race_uuid,
                            'folder': race_parent_folder,
                            'files': list(race_parent_folder.rglob("*.lsx")),
                            'source_file': races_file
                        }
                        

                        race_found = True
                        
                except Exception as e:
                    pass
        
        if not race_found:
            pass
    
    def parse_appearance_data(self, appearance_folder: Path):
        """解析外观数据"""
        
        # 查找外观配置文件
        appearance_file_patterns = [
            "CharacterCreationAppearanceVisuals.lsx",
            "*Appearance*.lsx",
            "*Visual*.lsx",
            "*Creation*.lsx"
        ]
        
        appearance_found = False
        processed_files = set()  # 避免重复处理
        vanilla_races_found = set()  # 记录原版种族UUID
        
        for pattern in appearance_file_patterns:
            appearance_files = list(appearance_folder.rglob(pattern))
            
            if appearance_files:
                
                for appearance_file in appearance_files:
                    # 避免重复处理
                    relative_path = appearance_file.relative_to(appearance_folder)
                    if relative_path in processed_files:
                        continue
                        
                    try:
                        content = appearance_file.read_text(encoding='utf-8')
                        
                        # 检查外观内容
                        if any(keyword in content for keyword in ['VisualResource', 'RaceUUID', 'BodyShape', 'Head']):
                            # 检测原版种族
                            import re
                            # XML格式
                            race_uuid_pattern1 = r'<attribute id="RaceUUID"[^>]*value="([a-f0-9-]{36})"[^>]*/?>'
                            # 引号格式
                            race_uuid_pattern2 = r'RaceUUID="([a-f0-9-]{36})"'
                            
                            race_matches = []
                            race_matches.extend(re.findall(race_uuid_pattern1, content, re.IGNORECASE))
                            race_matches.extend(re.findall(race_uuid_pattern2, content, re.IGNORECASE))
                            
                            for race_uuid in race_matches:
                                if is_vanilla_race(race_uuid):
                                    vanilla_races_found.add(race_uuid)
                            
                            # 文件名标识
                            appearance_key = f"{appearance_folder.name}_{appearance_file.stem}"
                            
                            # 处理重名
                            original_key = appearance_key
                            counter = 1
                            while appearance_key in self.appearance_data:
                                appearance_key = f"{original_key}_{counter}"
                                counter += 1
                            
                            # 找pak路径
                            pak_path = None
                            for selected_pak in self.selected_appearance_paks:
                                pak_name = Path(selected_pak).stem
                                if pak_name == appearance_folder.name:
                                    pak_path = selected_pak
                                    break
                            
                            self.appearance_data[appearance_key] = {
                                'file': str(relative_path),
                                'content': content,
                                'folder': str(appearance_folder.relative_to(Path.cwd())),
                                'pak_path': pak_path
                            }
                            

                            appearance_found = True
                            processed_files.add(relative_path)
                            
                    except Exception as e:
                        pass
        
        # 查找所有lsx文件
        if not appearance_found:
            all_lsx_files = list(appearance_folder.rglob("*.lsx"))
            
            for lsx_file in all_lsx_files:
                # 避免重复处理
                relative_lsx_path = lsx_file.relative_to(appearance_folder)
                if relative_lsx_path in processed_files:
                    continue
                    
                try:
                    content = lsx_file.read_text(encoding='utf-8')
                    
                    # 检查外观相关内容
                    if any(keyword in content for keyword in ['VisualResource', 'CharacterCreation', 'Head', 'Hair']):
                        # 检测原版种族UUID
                        # XML格式
                        race_uuid_pattern1 = r'<attribute id="RaceUUID"[^>]*value="([a-f0-9-]{36})"[^>]*/?>' 
                        # 引号格式
                        race_uuid_pattern2 = r'RaceUUID="([a-f0-9-]{36})"'
                        
                        race_matches = []
                        race_matches.extend(re.findall(race_uuid_pattern1, content, re.IGNORECASE))
                        race_matches.extend(re.findall(race_uuid_pattern2, content, re.IGNORECASE))
                        
                        for race_uuid in race_matches:
                            if is_vanilla_race(race_uuid):
                                vanilla_races_found.add(race_uuid)
                        
                        # 用文件名做标识
                        appearance_key = f"{appearance_folder.name}_{lsx_file.stem}"
                        
                        # 处理重名
                        original_key = appearance_key
                        counter = 1
                        while appearance_key in self.appearance_data:
                            appearance_key = f"{original_key}_{counter}"
                            counter += 1
                        
                        # 找pak路径
                        pak_path = None
                        for selected_pak in self.selected_appearance_paks:
                            pak_name = Path(selected_pak).stem
                            if pak_name == appearance_folder.name:
                                pak_path = selected_pak
                                break
                        
                        self.appearance_data[appearance_key] = {
                            'file': str(relative_lsx_path),
                            'content': content,
                            'folder': str(appearance_folder.relative_to(Path.cwd())),
                            'pak_path': pak_path
                        }
                        

                        appearance_found = True
                        processed_files.add(relative_lsx_path)
                        
                except Exception as e:
                    pass
        
        if not appearance_found:
            pass
        
        # 保存检测到的原版种族
        # 找对应pak文件
        pak_path = None
        for selected_pak in self.selected_appearance_paks:
            pak_name = Path(selected_pak).stem
            if pak_name == appearance_folder.name:
                pak_path = selected_pak
                break
        
        if pak_path and vanilla_races_found:
            self.appearance_vanilla_races[pak_path] = list(vanilla_races_found)
    
    def create_compatibility_patches(self):
        """创建兼容性补丁"""

        

        
        if not self.race_data or not self.appearance_data:
            raise Exception("没有找到有效的种族或外观数据")
        
        # 使用用户输入的信息
        mod_name = self.patch_info['mod_name']
        author = self.patch_info['author']
        
        # 清理输出目录
        if self.output_dir.exists():
            for item in self.output_dir.iterdir():
                if item.is_dir():
                    try:
                        shutil.rmtree(item)
                    except:
                        pass
        
        # 创建目录
        output_mod_dir = self.output_dir / mod_name
        output_mod_dir.mkdir(parents=True, exist_ok=True)
        
        # 创建MOD结构
        mods_dir = output_mod_dir / "Mods" / mod_name
        public_dir = output_mod_dir / "Public" / mod_name / "CharacterCreation"
        mods_dir.mkdir(parents=True, exist_ok=True)
        public_dir.mkdir(parents=True, exist_ok=True)
        
        # 处理UUID
        if (self.patch_info['regenerate_uuid'] or 
            not hasattr(self, 'fixed_uuid') or 
            not self.fixed_uuid or 
            self.fixed_uuid == "12345678-1234-5678-9abc-123456789012"):
            mod_uuid = self.generate_bg3_uuid()
            self.fixed_uuid = mod_uuid
        else:
            mod_uuid = self.fixed_uuid
            
        self.create_meta_file(mods_dir / "meta.lsx", mod_name, author, mod_uuid)
        
        # 生成配置
        self.create_appearance_compatibility(public_dir / "CharacterCreationAppearanceVisuals.lsx")
        

    
    def version_to_version64(self, version_str: str) -> int:
        """转换版本号为BG3格式"""
        version_parts = version_str.split('.')
        major = int(version_parts[0]) if len(version_parts) > 0 else 1
        minor = int(version_parts[1]) if len(version_parts) > 1 else 0
        revision = int(version_parts[2]) if len(version_parts) > 2 else 0
        build = int(version_parts[3]) if len(version_parts) > 3 else 0
        
        # BG3版本号格式
        version64 = (major << 55) | (minor << 47) | (revision << 31) | (build << 16)
        return version64
    
    def create_meta_file(self, meta_path: Path, mod_name: str, author: str, mod_uuid: str):
        """创建meta文件"""
        # 获取用户信息
        description = getattr(self, 'patch_info', {}).get('description', 'Auto-generated compatibility patch for selected races and appearance mods')
        version = getattr(self, 'patch_info', {}).get('version', '1.0.0.0')
        
        # 转换版本号
        version64 = self.version_to_version64(version)
        
        meta_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<save>
    <version major="4" minor="0" revision="9" build="328"/>
    <region id="Config">
        <node id="root">
            <children>
                <node id="Dependencies"/>
                <node id="ModuleInfo">
                    <attribute id="Author" type="LSString" value="{author}"/>
                    <attribute id="CharacterCreationLevelName" type="FixedString" value=""/>
                    <attribute id="Description" type="LSString" value="{description}"/>
                    <attribute id="Folder" type="LSString" value="{mod_name}"/>
                    <attribute id="LobbyLevelName" type="FixedString" value=""/>
                    <attribute id="MD5" type="LSString" value=""/>
                    <attribute id="MainMenuBackgroundVideo" type="FixedString" value=""/>
                    <attribute id="MenuLevelName" type="FixedString" value=""/>
                    <attribute id="Name" type="LSString" value="{mod_name}"/>
                    <attribute id="NumPlayers" type="uint8" value="4"/>
                    <attribute id="PhotoBooth" type="FixedString" value=""/>
                    <attribute id="StartupLevelName" type="FixedString" value=""/>
                    <attribute id="Tags" type="LSString" value=""/>
                    <attribute id="Type" type="FixedString" value="Add-on"/>
                    <attribute id="UUID" type="FixedString" value="{mod_uuid}"/>
                    <attribute id="Version64" type="int64" value="{version64}"/>
                    <children>
                        <node id="PublishVersion">
                            <attribute id="Version64" type="int64" value="{version64}"/>
                        </node>
                        <node id="TargetModes">
                            <children>
                                <node id="Target">
                                    <attribute id="Object" type="FixedString" value="Story"/>
                                </node>
                            </children>
                        </node>
                    </children>
                </node>
            </children>
        </node>
    </region>
</save>'''
        
        meta_path.write_text(meta_content, encoding='utf-8')

    
    def create_appearance_compatibility(self, output_file: Path):
        """创建外观兼容性配置"""
        if not self.appearance_data:
            return
            
        # 收集配置 - 按种族分组，每个种族内按外观排序
        all_race_configs = []
        
        # 准备外观数据
        valid_appearances = []
        for appearance_key, appearance_info in self.appearance_data.items():
            pak_path = appearance_info.get('pak_path', '')
            if pak_path in self.appearance_race_selections:
                selected_race_uuid = self.appearance_race_selections[pak_path]
                race_info = VANILLA_RACE_MAPPING.get(selected_race_uuid.lower())
                if race_info:
                    valid_appearances.append({
                        'key': appearance_key,
                        'info': appearance_info,
                        'pak_path': pak_path,
                        'selected_race_uuid': selected_race_uuid,
                        'race_name': race_info['name_en']
                    })
        
        # 按种族循环，每个种族内循环所有外观
        if self.race_data:
            for race_key, race_info_data in self.race_data.items():
                race_uuid = race_info_data['uuid']
                
                # 为当前种族生成所有外观配置
                for appearance in valid_appearances:
                    appearance_content = appearance['info']['content']
                    race_name = appearance['race_name']
                    selected_race_uuid = appearance['selected_race_uuid']
                    
                    # 处理外观配置，保持原始种族UUID不变
                    race_config = self.process_appearance_for_race(appearance_content, race_name, selected_race_uuid, race_uuid)
                    if race_config:
                        all_race_configs.append(race_config)
        else:
            # 没有种族数据时，按外观顺序生成
            for appearance in valid_appearances:
                appearance_content = appearance['info']['content']
                race_name = appearance['race_name']
                selected_race_uuid = appearance['selected_race_uuid']
                
                race_config = self.process_appearance_for_race(appearance_content, race_name, selected_race_uuid, None)
                if race_config:
                    all_race_configs.append(race_config)
    
        
        if all_race_configs:
            # 构建XML内容
            xml_header = '<?xml version="1.0" encoding="utf-8"?>\n<save>\n    <version major="4" minor="0" revision="9" build="331" />\n    <region id="CharacterCreationAppearanceVisuals">\n        <node id="root">\n            <children>'
            xml_footer = '\n            </children>\n        </node>\n    </region>\n</save>'
            
            # 合并配置
            combined_content = xml_header + '\n' + '\n'.join(all_race_configs) + xml_footer
            
            # 确保目录存在
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            # 写入文件
            output_file.write_text(combined_content, encoding='utf-8')
    
    def process_appearance_for_race(self, appearance_content: str, race_name: str, race_uuid: str, target_race_uuid: str = None) -> str:
        """处理外观配置"""
        try:
            # 提取配置主体
            start_marker = '<children>'
            end_marker = '</children>'
            
            start_idx = appearance_content.find(start_marker)
            end_idx = appearance_content.find(end_marker)
            
            if start_idx == -1 or end_idx == -1:
                return ""
            
            start_idx += len(start_marker)
            config_body = appearance_content[start_idx:end_idx]
            
            if not config_body.strip():
                return ""
            
            # 解析所有CharacterCreationAppearanceVisual节点
            import re
            # 匹配完整节点
            node_pattern = r'<node id="CharacterCreationAppearanceVisual"[^>]*>([\s\S]*?)</node>'
            node_matches = re.finditer(node_pattern, config_body, re.DOTALL)
            
            filtered_nodes = []
            for match in node_matches:
                full_node_content = match.group(1)  # 完整的节点内容
                
                # 分离描述文本和属性内容
                # 查找第一个<attribute标签的位置
                first_attr_match = re.search(r'<attribute', full_node_content)
                if first_attr_match:
                    # 描述文本是第一个<attribute之前的内容
                    description_part = full_node_content[:first_attr_match.start()]
                    attributes_part = full_node_content[first_attr_match.start():]
                else:
                    # 没属性就全是描述
                    description_part = full_node_content
                    attributes_part = ""
                
                # 检查节点中的RaceUUID是否匹配目标种族
                race_uuid_match = re.search(r'<attribute id="RaceUUID"[^>]*value="([^"]+)"', attributes_part)
                if race_uuid_match:
                    node_race_uuid = race_uuid_match.group(1)
                    # RaceUUID匹配就包含
                    if node_race_uuid.lower() == race_uuid.lower():
                        # 替换UUID为新生成的UUID（保持每个节点的UUID唯一）
                        def replace_uuid(match):
                            return f'{match.group(1)}{self.generate_bg3_uuid()}{match.group(2)}'
                        
                        uuid_pattern = r'(<attribute id="UUID" type="guid" value=")[^"]+(")'
                        processed_attributes = re.sub(uuid_pattern, replace_uuid, attributes_part)
                        
                        # 有目标UUID就替换
                        if target_race_uuid:
                            def replace_race_uuid(match):
                                return f'{match.group(1)}{target_race_uuid}{match.group(2)}'
                            
                            race_uuid_pattern = r'(<attribute id="RaceUUID"[^>]*value=")[^"]+(")'
                            processed_attributes = re.sub(race_uuid_pattern, replace_race_uuid, processed_attributes)
                        
                        # 检查并修复错误的IconIdOverride
                        slot_name_match = re.search(r'<attribute id="SlotName"[^>]*value="([^"]+)"', processed_attributes)
                        visual_resource_match = re.search(r'<attribute id="VisualResource"[^>]*value="([^"]+)"', processed_attributes)
                        body_type_match = re.search(r'<attribute id="BodyType"[^>]*value="([^"]+)"', processed_attributes)
                        icon_override_match = re.search(r'<attribute id="IconIdOverride"[^>]*value="([^"]+)"', processed_attributes)
                        
                        if slot_name_match and visual_resource_match:
                            slot_name = slot_name_match.group(1)
                            visual_resource_uuid = visual_resource_match.group(1)
                            body_type = body_type_match.group(1) if body_type_match else "1"
                            
                            # 生成正确的IconIdOverride格式：{BodyType}_{SlotName}_{VisualResourceUUID}
                            correct_icon_id = f"{body_type}_{slot_name}_{visual_resource_uuid}"
                            
                            # 检查现有的IconIdOverride是否需要修复
                            need_fix = False
                            if icon_override_match:
                                existing_icon_id = icon_override_match.group(1)
                                # 检查格式是否有问题
                                if ("Horns" in existing_icon_id or 
                                    "Horn" in existing_icon_id or
                                    not existing_icon_id.startswith(f"{body_type}_{slot_name}_") or
                                    existing_icon_id != correct_icon_id):
                                    # 正确格式就不改
                                    expected_pattern = rf"^{body_type}_{slot_name}_[a-f0-9\-]{{36}}$"
                                    if not re.match(expected_pattern, existing_icon_id, re.IGNORECASE):
                                        need_fix = True
                            else:
                                # 没有就添加
                                need_fix = True
                            
                            if need_fix:
                                icon_override_pattern = r'<attribute id="IconIdOverride"[^>]*value="[^"]+"[^>]*/>'
                                if re.search(icon_override_pattern, processed_attributes):
                                    # 有就替换
                                    def replace_icon_override(match):
                                        return f'<attribute id="IconIdOverride" type="FixedString" value="{correct_icon_id}"/>'
                                    processed_attributes = re.sub(icon_override_pattern, replace_icon_override, processed_attributes)
                                else:
                                    # 没有就在SlotName后加
                                    slot_name_pattern = r'(<attribute id="SlotName"[^>]*/>)'
                                    def add_icon_override(match):
                                        return f'{match.group(1)}\n                    <attribute id="IconIdOverride" type="FixedString" value="{correct_icon_id}"/>'
                                    processed_attributes = re.sub(slot_name_pattern, add_icon_override, processed_attributes)
                        
                        # 重建节点
                        # 为属性行添加适当的缩进
                        if processed_attributes:
                            indented_attributes = '\n'.join(['                    ' + line.strip() for line in processed_attributes.split('\n') if line.strip()])
                        else:
                            indented_attributes = ""
                        
                        # 构建节点
                        if description_part.strip():
                            # 去掉末尾换行
                            clean_description = description_part.rstrip()
                            if indented_attributes:
                                complete_node = f'                <node id="CharacterCreationAppearanceVisual">{clean_description}\n{indented_attributes}\n                </node>'
                            else:
                                complete_node = f'                <node id="CharacterCreationAppearanceVisual">{clean_description}\n                </node>'
                        else:
                            if indented_attributes:
                                complete_node = f'                <node id="CharacterCreationAppearanceVisual">\n{indented_attributes}\n                </node>'
                            else:
                                complete_node = f'                <node id="CharacterCreationAppearanceVisual">\n                </node>'
                        
                        filtered_nodes.append(complete_node)
            
            if filtered_nodes:
                return '\n'.join(filtered_nodes)
            else:
                return ""
            
        except Exception as e:
            return ""
    
    def pack_mod(self):
        """打包MOD"""
        mod_name = self.patch_info.get('mod_name', '').strip() or "Auto_Generated_Compatibility"
        mod_dir = self.output_dir / mod_name
        pak_file = self.output_dir / f"{mod_name}.pak"
        
        # 删除旧的pak文件
        if self.output_dir.exists():
            for item in self.output_dir.iterdir():
                if item.is_file() and item.suffix == '.pak':
                    try:
                        item.unlink()
                    except:
                        pass
        
        try:
            # 检查目录
            if not mod_dir.exists():
                raise Exception(f"MOD目录不存在: {mod_dir}")
                
            # 使用Divine.exe打包
            cmd = [
                str(self.divine_exe),
                "-g", "bg3",
                "--action", "create-package",
                "--source", str(mod_dir),
                "--destination", str(pak_file),
                "-l", "all"
            ]
            
            # 隐藏控制台窗口
            creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.divine_exe.parent, creationflags=creation_flags)
            
            # 记录输出
            if result.stdout:
                pass
            
            if result.stderr:
                pass
            
            if result.returncode != 0:
                error_msg = result.stderr if result.stderr else result.stdout
                raise Exception(f"Divine.exe打包失败 (返回码: {result.returncode}): {error_msg}")
            
            # 检查pak文件
            if not pak_file.exists():
    
                raise Exception(f"打包后的pak文件不存在: {pak_file}")
                

            
            # 创建ZIP压缩包
            self.create_zip_package(pak_file, mod_dir, mod_name)
            
        except Exception as e:
            raise Exception(f"打包MOD失败: {e}")
    
    def create_zip_package(self, pak_file: Path, mod_dir: Path, mod_name: str):
        """创建ZIP压缩包"""
        try:
    
            
            # 创建临时目录
            temp_dir = self.output_dir / "temp"
            temp_dir.mkdir(exist_ok=True)
            
            # 复制PAK文件
            temp_pak = temp_dir / pak_file.name
            shutil.copy2(pak_file, temp_pak)
            
            # 计算MD5
            md5_hash = self.calculate_md5(pak_file)

            
            # 读取MOD信息
            meta_file = mod_dir / "Mods" / mod_name / "meta.lsx"
            mod_uuid, mod_version = self.extract_mod_info(meta_file)
            
            # 创建info.json
            info_data = {
                "mods": [
                    {
                        "modName": "",
                        "UUID": mod_uuid,
                        "folderName": mod_name,
                        "version": mod_version,
                        "MD5": md5_hash
                    }
                ]
            }
            
            info_file = temp_dir / "info.json"
            with open(info_file, 'w', encoding='utf-8') as f:
                json.dump(info_data, f, indent=4, ensure_ascii=False)
            
            pass
            
            # 创建ZIP文件
            zip_file = self.output_dir / f"{mod_name}.zip"
            with zipfile.ZipFile(zip_file, 'w', zipfile.ZIP_DEFLATED) as zf:
                # 添加PAK文件
                zf.write(temp_pak, pak_file.name)
                # 添加info.json
                zf.write(info_file, "info.json")
            

            
            # 清理临时目录
            shutil.rmtree(temp_dir)
            
        except Exception as e:

            # 清理临时目录
            temp_dir = self.output_dir / "temp"
            if temp_dir.exists():
                shutil.rmtree(temp_dir)
    

    
    def calculate_md5(self, file_path: Path) -> str:
        """计算MD5"""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest().upper()
    
    def extract_mod_info(self, meta_file: Path) -> tuple[str, str]:
        """从meta.lsx文件中提取UUID和版本信息"""
        try:
            with open(meta_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 找UUID
            uuid_match = re.search(r'<attribute id="UUID" type="FixedString" value="([^"]+)"', content)
            mod_uuid = uuid_match.group(1) if uuid_match else self.generate_bg3_uuid()
            
            # 找版本号
            version_match = re.search(r'<attribute id="Version" type="int64" value="([^"]+)"', content)
            mod_version = version_match.group(1) if version_match else "1"
            
            return mod_uuid, mod_version
            
        except Exception as e:

            return self.generate_bg3_uuid(), "1"
    
    def center_window(self):
        """窗口居中"""
        self.root.update_idletasks()  # 等窗口算好尺寸
        
        # 固定窗口大小
        window_width = 800
        window_height = 640
        
        # 屏幕大小
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        
        # 算居中位置
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        
        # 设置位置
        self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")
    
    def run(self):
        """启动程序"""



        self.root.mainloop()

def main():
    """主入口"""
    try:
        app = BG3CompatibilityGenerator()
        app.run()
    except Exception as e:
        print(f"启动失败: {e}")
        import traceback
        traceback.print_exc()
        input("按回车键退出...")

if __name__ == "__main__":
    main()