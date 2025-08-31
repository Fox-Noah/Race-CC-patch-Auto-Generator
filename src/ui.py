#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BG3 MOD兼容性工具 - UI模块
用户界面相关的类和方法
"""

import os
import sys
import threading
import webbrowser
import sys
import shutil
import queue
from pathlib import Path

try:
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox, scrolledtext
    from tkinter.ttk import Progressbar
except ImportError:
    print("错误：无法导入tkinter。请确保Python安装包含tkinter模块。")
    sys.exit(1)

def get_application_path():
    """获取程序路径，支持开发和打包环境"""
    if getattr(sys, 'frozen', False):
        # 打包exe
        return Path(sys.executable).parent
    else:
        # 开发模式
        return Path(__file__).parent.parent

class PatchInfoDialog:
    """补丁信息对话框"""
    def __init__(self, parent, existing_meta_info=None):
        self.parent = parent
        self.result = None
        self.existing_meta_info = existing_meta_info or {
            'exists': False,
            'mod_name': '',
            'author': '',
            'description': '',
            'version': '',
            'uuid': '',
            'regenerate_uuid': True
        }
        
        # 记录原始名称
        self.original_mod_name = self.existing_meta_info['mod_name'] or "Auto_Generated_Compatibility"
        
        self.dialog = tk.Toplevel(parent.root)
        self.dialog.title("meta.lsx")
        self.dialog.geometry("500x400")
        self.dialog.resizable(False, False)
        self.dialog.transient(parent.root)
        self.dialog.grab_set()
        
        self.create_widgets()
        
        # 居中显示
        self.center_dialog()
        
        # 设置图标
        # 打包后图标位置
        if getattr(sys, 'frozen', False):
            # 打包版
            icon_path = Path(sys._MEIPASS) / "打包图标.ico"
        else:
            # 开发版
            app_dir = get_application_path()
            icon_path = app_dir / "src" / "asset" / "image" / "打包图标.ico"
        if icon_path.exists():
            self.dialog.iconbitmap(str(icon_path))
        
    def create_widgets(self):
        """创建对话框界面"""
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 设置默认值
        default_mod_name = self.existing_meta_info['mod_name'] or "Auto_Generated_Compatibility"
        default_author = self.existing_meta_info['author'] or "BG3 Compatibility Generator"
        default_description = self.existing_meta_info['description'] or "Auto-generated compatibility patch for selected races and appearance mods"
        default_version = self.existing_meta_info['version'] or "1.0.0.0"
        default_regenerate_uuid = self.existing_meta_info['regenerate_uuid']
        
        # MOD名称
        ttk.Label(main_frame, text=self.parent.texts.get("label_mod_name", "MOD名称:")).grid(row=0, column=0, sticky=tk.W, pady=(0, 15), padx=(0, 15))
        self.mod_name_var = tk.StringVar(value=default_mod_name)
        self.mod_name_entry = ttk.Entry(main_frame, textvariable=self.mod_name_var, width=40)
        self.mod_name_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=(0, 15))
        
        # 作者
        ttk.Label(main_frame, text=self.parent.texts.get("label_author", "作者:")).grid(row=1, column=0, sticky=tk.W, pady=(0, 15), padx=(0, 15))
        self.author_var = tk.StringVar(value=default_author)
        self.author_entry = ttk.Entry(main_frame, textvariable=self.author_var, width=40)
        self.author_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=(0, 15))
        
        # 描述
        ttk.Label(main_frame, text=self.parent.texts.get("label_description", "描述:")).grid(row=2, column=0, sticky=(tk.W, tk.N), pady=(0, 15), padx=(0, 15))
        self.description_text = scrolledtext.ScrolledText(main_frame, width=40, height=5, wrap=tk.WORD)
        self.description_text.grid(row=2, column=1, sticky=(tk.W, tk.E), pady=(0, 15))
        self.description_text.insert(tk.END, default_description)
        
        # 版本
        ttk.Label(main_frame, text=self.parent.texts.get("label_version", "版本:")).grid(row=3, column=0, sticky=tk.W, pady=(0, 15), padx=(0, 15))
        self.version_var = tk.StringVar(value=default_version)
        self.version_entry = ttk.Entry(main_frame, textvariable=self.version_var, width=40)
        self.version_entry.grid(row=3, column=1, sticky=(tk.W, tk.E), pady=(0, 15))
        
        # UUID选项
        self.regenerate_uuid_var = tk.BooleanVar(value=default_regenerate_uuid)
        self.regenerate_uuid_check = ttk.Checkbutton(main_frame, 
                                                    text=self.parent.texts.get("regenerate_uuid", "重新生成UUID（推荐）"),
                                                    variable=self.regenerate_uuid_var)
        self.regenerate_uuid_check.grid(row=4, column=0, columnspan=2, sticky=tk.W, pady=(0, 20))
        
        # 按钮
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=5, column=0, columnspan=2, pady=(20, 0))
        
        self.ok_button = ttk.Button(button_frame, text=self.parent.texts.get("ok_button", "确定"), 
                                   command=self.ok_clicked, style='Accent.TButton')
        self.ok_button.pack(side=tk.LEFT, padx=(0, 15))
        
        self.cancel_button = ttk.Button(button_frame, text=self.parent.texts.get("cancel_button", "取消"), 
                                       command=self.cancel_clicked)
        self.cancel_button.pack(side=tk.LEFT)
        
        # 设置网格权重
        main_frame.columnconfigure(1, weight=1)
        
        # 监听MOD名称变化
        self.mod_name_var.trace('w', self.on_mod_name_changed)
        
    def on_mod_name_changed(self, *args):
        """MOD名称变化时的处理"""
        current_name = self.mod_name_var.get().strip()
        
        # 如果当前名称为空或者是默认名称，则使用原始名称
        if not current_name or current_name == "Auto_Generated_Compatibility":
            # 如果描述还是默认的，则更新描述
            current_description = self.description_text.get(1.0, tk.END).strip()
            if current_description == "Auto-generated compatibility patch for selected races and appearance mods":
                new_description = f"Auto-generated compatibility patch for selected races and appearance mods"
                self.description_text.delete(1.0, tk.END)
                self.description_text.insert(1.0, new_description)
        else:
            # 如果描述还是默认的，则根据新名称更新描述
            current_description = self.description_text.get(1.0, tk.END).strip()
            if current_description == "Auto-generated compatibility patch for selected races and appearance mods" or \
               current_description.startswith("Auto-generated compatibility patch for"):
                new_description = f"Auto-generated compatibility patch for selected races and appearance mods"
                self.description_text.delete(1.0, tk.END)
                self.description_text.insert(1.0, new_description)
    
    def center_dialog(self):
        """居中显示对话框"""
        self.dialog.update_idletasks()
        
        # 获取屏幕尺寸
        screen_width = self.dialog.winfo_screenwidth()
        screen_height = self.dialog.winfo_screenheight()
        
        # 获取窗口尺寸
        window_width = self.dialog.winfo_width()
        window_height = self.dialog.winfo_height()
        
        # 计算居中位置
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        
        # 设置窗口位置
        self.dialog.geometry(f"+{x}+{y}")
    
    def ok_clicked(self):
        """确定按钮点击处理"""
        self.result = {
            'mod_name': self.mod_name_var.get().strip() or "Auto_Generated_Compatibility",
            'author': self.author_var.get().strip() or "BG3 Compatibility Generator",
            'description': self.description_text.get(1.0, tk.END).strip() or "Auto-generated compatibility patch for selected races and appearance mods",
            'version': self.version_var.get().strip() or "1.0.0.0",
            'regenerate_uuid': self.regenerate_uuid_var.get()
        }
        self.dialog.destroy()
    
    def cancel_clicked(self):
        """取消按钮点击处理"""
        self.result = None
        self.dialog.destroy()

class UIManager:
    """UI管理器，包含所有UI相关的方法"""
    
    def __init__(self, app):
        self.app = app
    
    def on_language_change(self, event=None):
        """语言切换处理"""
        selected = self.app.language_var.get()
        if selected == "中文":
            self.app.change_language("zh_CN")
        elif selected == "English":
            self.app.change_language("en_US")
    
    def select_race_paks(self):
        """选择种族pak文件"""
        if self.app.is_task_running:
            messagebox.showwarning(self.app.texts.get("warning_title", "警告"), self.app.texts.get("warning_task_running", "有任务正在运行，请等待完成后再操作"))
            return
            
        files = filedialog.askopenfilenames(
            title=self.app.texts.get("select_race_dialog_title", "选择种族MOD pak文件"),
            filetypes=[(self.app.texts.get("file_types_pak", "PAK文件"), "*.pak"), (self.app.texts.get("file_types_all", "所有文件"), "*.*")],
            multiple=True
        )
        
        if files:
            self.app.is_task_running = True
            self.app.current_task_thread = threading.Thread(
                target=self.app._import_and_extract_files_async,
                args=(files, self.app.sourcemod_dir, "种族")
            )
            self.app.current_task_thread.daemon = True
            self.app.current_task_thread.start()
    
    def select_appearance_paks(self):
        """选择外观pak文件并复制到Panagway文件夹"""
        if self.app.is_task_running:
            messagebox.showwarning(self.app.texts.get("warning_title", "警告"), self.app.texts.get("warning_task_running", "有任务正在运行，请等待完成后再操作"))
            return
            
        files = filedialog.askopenfilenames(
            title=self.app.texts.get("select_appearance_dialog_title", "选择外观MOD pak文件"),
            filetypes=[(self.app.texts.get("file_types_pak", "PAK文件"), "*.pak"), (self.app.texts.get("file_types_all", "所有文件"), "*.*")],
            multiple=True
        )
        
        if files:
            self.app.is_task_running = True
            self.app.current_task_thread = threading.Thread(
                target=self.app._import_and_extract_files_async,
                args=(files, self.app.panagway_dir, "外观")
            )
            self.app.current_task_thread.daemon = True
            self.app.current_task_thread.start()
    
    def create_widgets(self):
        """创建界面"""
        # 主框架
        main_frame = ttk.Frame(self.app.root, padding=(20, 20, 20, 2))  # 左上右下
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 网格权重
        self.app.root.columnconfigure(0, weight=1)
        self.app.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        
        # 标题语言区域
        title_frame = ttk.Frame(main_frame)
        title_frame.grid(row=0, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 30))
        title_frame.columnconfigure(0, weight=1)
        
        # 标题
        self.title_label = ttk.Label(title_frame, text=self.app.texts.get("window_title", "博德之门3 MOD兼容性自动生成工具"), 
                                    font=('Arial', 16, 'bold'))
        self.title_label.grid(row=0, column=0, sticky=tk.W)
        
        # 语言选择
        language_frame = ttk.Frame(title_frame)
        language_frame.grid(row=0, column=1, sticky=tk.E)
        
        self.language_label = ttk.Label(language_frame, text=self.app.texts.get("language_label", "语言:"))
        self.language_label.pack(side=tk.LEFT, padx=(0, 10))
        
        self.app.language_var = tk.StringVar(value="中文" if self.app.current_language == "zh_CN" else "English")
        self.language_combo = ttk.Combobox(language_frame, textvariable=self.app.language_var, 
                                          values=["中文", "English"], state="readonly", width=10)
        self.language_combo.pack(side=tk.LEFT)
        self.language_combo.bind("<<ComboboxSelected>>", self.on_language_change)
        
        # 种族pak区域
        self.app.race_frame = ttk.LabelFrame(main_frame, text=self.app.texts.get("race_frame_title", "选择种族MOD (.pak文件)"), padding="15")
        self.app.race_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 20))
        self.app.race_frame.columnconfigure(1, weight=1)
        
        self.app.race_button = ttk.Button(self.app.race_frame, text=self.app.texts.get("select_race_paks", "选择种族pak文件"), 
                                     command=self.select_race_paks)
        self.app.race_button.grid(row=0, column=0, padx=(0, 15))
        
        self.app.race_listbox = tk.Listbox(self.app.race_frame, height=4)
        self.app.race_listbox.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 15))
        self.app.race_listbox.bind("<Button-3>", self.show_race_context_menu)  # 右键菜单
        
        race_scrollbar = ttk.Scrollbar(self.app.race_frame, orient="vertical", command=self.app.race_listbox.yview)
        race_scrollbar.grid(row=0, column=2, sticky=(tk.N, tk.S))
        self.app.race_listbox.configure(yscrollcommand=race_scrollbar.set)
        
        self.app.race_clear_button = ttk.Button(self.app.race_frame, text=self.app.texts.get("clear_button", "清除"), 
                                           command=self.app.clear_race_selection)
        self.app.race_clear_button.grid(row=0, column=3, padx=(15, 0))
        
        # 外观pak区域
        self.app.appearance_frame = ttk.LabelFrame(main_frame, text=self.app.texts.get("appearance_frame_title", "选择外观MOD (.pak文件)"), padding="15")
        self.app.appearance_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 20))
        self.app.appearance_frame.columnconfigure(1, weight=1)
        
        # 外观按钮
        appearance_button_frame = ttk.Frame(self.app.appearance_frame)
        appearance_button_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        self.app.appearance_button = ttk.Button(appearance_button_frame, text=self.app.texts.get("select_appearance_paks", "选择外观pak文件"), 
                                           command=self.select_appearance_paks)
        self.app.appearance_button.pack(side=tk.LEFT, padx=(0, 15))
        
        self.app.appearance_clear_button = ttk.Button(appearance_button_frame, text=self.app.texts.get("clear_button", "清除"), 
                                                 command=self.app.clear_appearance_selection)
        self.app.appearance_clear_button.pack(side=tk.LEFT)
        
        # 外观显示区域
        self.app.appearance_canvas = tk.Canvas(self.app.appearance_frame, height=120, highlightthickness=0)
        self.app.appearance_canvas.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        appearance_scrollbar = ttk.Scrollbar(self.app.appearance_frame, orient="vertical", command=self.app.appearance_canvas.yview)
        appearance_scrollbar.grid(row=1, column=2, sticky=(tk.N, tk.S))
        self.app.appearance_canvas.configure(yscrollcommand=appearance_scrollbar.set)
        
        # 滚动框架
        self.app.appearance_scroll_frame = ttk.Frame(self.app.appearance_canvas)
        self.app.appearance_canvas_window = self.app.appearance_canvas.create_window((0, 0), window=self.app.appearance_scroll_frame, anchor="nw")
        
        # 滚动事件
        self.app.appearance_scroll_frame.bind("<Configure>", self.on_appearance_frame_configure)
        self.app.appearance_canvas.bind("<Configure>", self.on_appearance_canvas_configure)
        
        # 操作按钮
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=3, column=0, columnspan=3, pady=(20, 0))
        
        self.app.generate_button = ttk.Button(button_frame, text=self.app.texts.get("generate_button", "生成兼容性补丁"), 
                                         command=self.app.generate_compatibility, 
                                         style='Accent.TButton')
        self.app.generate_button.pack(side=tk.LEFT, padx=(0, 15))
        
        self.app.open_dir_button = ttk.Button(button_frame, text=self.app.texts.get("open_output_dir", "打开输出目录"), 
                                         command=self.app.open_output_directory)
        self.app.open_dir_button.pack(side=tk.LEFT, padx=(0, 15))
        
        self.app.refresh_button = ttk.Button(button_frame, text=self.app.texts.get("refresh_pak_list", "刷新PAK列表"), 
                                        command=self.app.refresh_pak_lists)
        self.app.refresh_button.pack(side=tk.LEFT)
        
        # 进度条
        self.app.progress_var = tk.StringVar(value=self.app.texts.get("status_ready", "就绪"))
        ttk.Label(main_frame, textvariable=self.app.progress_var).grid(row=4, column=0, columnspan=3, pady=(20, 10))
        
        self.app.progress_bar = Progressbar(main_frame, mode='determinate')
        self.app.progress_bar.grid(row=5, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 15))
        
        # 分隔线
        separator = ttk.Separator(main_frame, orient='horizontal')
        separator.grid(row=6, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(15, 2))
        
        # 底部信息区域
        bottom_frame = ttk.Frame(main_frame)
        bottom_frame.grid(row=7, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 5))
        bottom_frame.columnconfigure(1, weight=1)
        
        # 作者署名
        author_label = ttk.Label(bottom_frame, text="@小D游戏试玩组   @XDynis", 
                                font=('Arial', 9), foreground='gray')
        author_label.grid(row=0, column=0, sticky=tk.W)
        
        # 支持按钮
        self.app.support_button = ttk.Button(bottom_frame, text=self.app.texts.get("support_button", "支持作者 ☕"), 
                                        command=self.open_support_link,
                                        style='Accent.TButton')
        self.app.support_button.grid(row=0, column=2, sticky=tk.E)
    

    
    def update_ui_texts(self):
        """更新界面文本"""
        # 更新窗口标题
        self.app.root.title(self.app.texts.get("window_title", "博德之门3 MOD兼容性自动生成工具"))
        
        # 更新标题标签
        self.title_label.config(text=self.app.texts.get("window_title", "博德之门3 MOD兼容性自动生成工具"))
        
        # 更新语言标签
        self.language_label.config(text=self.app.texts.get("language_label", "语言:"))
        
        # 更新种族框架
        self.app.race_frame.config(text=self.app.texts.get("race_frame_title", "选择种族MOD (.pak文件)"))
        self.app.race_button.config(text=self.app.texts.get("select_race_paks", "选择种族pak文件"))
        self.app.race_clear_button.config(text=self.app.texts.get("clear_button", "清除"))
        
        # 更新外观框架
        self.app.appearance_frame.config(text=self.app.texts.get("appearance_frame_title", "选择外观MOD (.pak文件)"))
        self.app.appearance_button.config(text=self.app.texts.get("select_appearance_paks", "选择外观pak文件"))
        self.app.appearance_clear_button.config(text=self.app.texts.get("clear_button", "清除"))
        
        # 更新按钮
        self.app.generate_button.config(text=self.app.texts.get("generate_button", "生成兼容性补丁"))
        self.app.open_dir_button.config(text=self.app.texts.get("open_output_dir", "打开输出目录"))
        self.app.refresh_button.config(text=self.app.texts.get("refresh_pak_list", "刷新PAK列表"))
        self.app.support_button.config(text=self.app.texts.get("support_button", "支持作者 ☕"))
        
        # 更新进度文本
        self.app.progress_var.set(self.app.texts.get("status_ready", "就绪"))
        
        # 更新外观种族选择下拉框
        self.app.refresh_appearance_race_comboboxes()
    
    def on_appearance_frame_configure(self, event):
        """外观滚动框架配置事件"""
        self.app.appearance_canvas.configure(scrollregion=self.app.appearance_canvas.bbox("all"))
    
    def on_appearance_canvas_configure(self, event):
        """外观画布配置事件"""
        canvas_width = event.width
        self.app.appearance_canvas.itemconfig(self.app.appearance_canvas_window, width=canvas_width)
    
    def show_race_context_menu(self, event):
        """显示种族列表框右键菜单"""
        try:
            # 获取点击位置的项目索引
            index = self.app.race_listbox.nearest(event.y)
            if index < self.app.race_listbox.size():
                # 选中该项目
                self.app.race_listbox.selection_clear(0, tk.END)
                self.app.race_listbox.selection_set(index)
                
                # 创建右键菜单
                context_menu = tk.Menu(self.app.root, tearoff=0)
                context_menu.add_command(label=self.app.texts.get("delete_file", "删除文件"), 
                                       command=lambda: self.app.delete_race_file(index))
                
                # 显示菜单
                context_menu.tk_popup(event.x_root, event.y_root)
        except Exception as e:
            pass
    
    def show_appearance_context_menu(self, event):
        """显示外观列表框右键菜单"""
        try:
            # 获取点击位置的项目索引
            index = self.app.appearance_listbox.nearest(event.y)
            if index < self.app.appearance_listbox.size():
                # 选中该项目
                self.app.appearance_listbox.selection_clear(0, tk.END)
                self.app.appearance_listbox.selection_set(index)
                
                # 创建右键菜单
                context_menu = tk.Menu(self.app.root, tearoff=0)
                context_menu.add_command(label=self.app.texts.get("delete_file", "删除文件"), 
                                       command=lambda: self.app.delete_appearance_file(index))
                
                # 显示菜单
                context_menu.tk_popup(event.x_root, event.y_root)
        except Exception as e:
            pass
    
    def open_support_link(self):
        """显示支持方式"""
        if self.app.current_language == "zh_CN":
            # 中文显示图片
            self.show_sponsor_dialog()
        else:
            # 英文打开链接
            try:
                webbrowser.open('https://ko-fi.com/X8X11KF0YO')
            except Exception as e:
                messagebox.showerror(self.app.texts.get("error_title", "错误"), 
                                   f"无法打开支持链接: {str(e)}")
    
    def delete_race_file(self, index):
        """删除指定索引的种族pak文件和对应的解包文件夹"""
        try:
            if 0 <= index < len(self.app.selected_race_paks):
                file_path = Path(self.app.selected_race_paks[index])
                file_name = file_path.name
                
                # 确认删除
                if messagebox.askyesno(self.app.texts.get("confirm_delete", "确认删除"), 
                                     self.app.texts.get("confirm_delete_message", f"确定要删除文件 {file_name} 吗？").format(file_name=file_name)):
                    # 删除pak文件
                    if file_path.exists():
                        file_path.unlink()
                    
                    # 删除对应的解包文件夹
                    extract_dir = self.app.sourcemod_dir / file_path.stem
                    if extract_dir.exists():
                        shutil.rmtree(extract_dir)
                    
                    # 刷新pak列表
                    self.app.refresh_pak_lists()
                    
                    messagebox.showinfo(self.app.texts.get("success", "成功"), 
                                      self.app.texts.get("delete_success", f"文件 {file_name} 已删除").format(file_name=file_name))
        except Exception as e:
            messagebox.showerror(self.app.texts.get("error", "错误"), 
                               self.app.texts.get("delete_error", f"删除文件时出错: {str(e)}"))
    
    def delete_appearance_file(self, index):
        """删除指定索引的外观pak文件和对应的解包文件夹"""
        try:
            if 0 <= index < len(self.app.selected_appearance_paks):
                file_path = Path(self.app.selected_appearance_paks[index])
                file_name = file_path.name
                
                # 确认删除
                if messagebox.askyesno(self.app.texts.get("confirm_delete", "确认删除"), 
                                     self.app.texts.get("confirm_delete_message", f"确定要删除文件 {file_name} 吗？").format(file_name=file_name)):
                    # 删除pak文件
                    if file_path.exists():
                        file_path.unlink()
                    
                    # 删除对应的解包文件夹
                    extract_dir = self.app.panagway_dir / file_path.stem
                    if extract_dir.exists():
                        shutil.rmtree(extract_dir)
                    
                    # 刷新pak列表
                    self.app.refresh_pak_lists()
                    
                    messagebox.showinfo(self.app.texts.get("success", "成功"), 
                                      self.app.texts.get("delete_success", f"文件 {file_name} 已删除").format(file_name=file_name))
        except Exception as e:
            messagebox.showerror(self.app.texts.get("error", "错误"), 
                               self.app.texts.get("delete_error", f"删除文件时出错: {str(e)}"))

    def clear_race_selection(self):
        """清除种族文件夹（删除Sourcemod文件夹内的所有内容）"""
        try:
            if not self.app.sourcemod_dir.exists():
                return
            
            # 检查文件夹是否有内容
            contents = list(self.app.sourcemod_dir.iterdir())
            if not contents:
                return
            
            count = len(contents)
            result = messagebox.askyesno(
                self.app.texts.get("confirm_delete_title", "确认删除"), 
                self.app.texts.get("confirm_delete_race_message", "确定要删除Sourcemod文件夹中的 {count} 个pak文件吗？\n此操作不可撤销！").format(count=count)
            )
            
            if result:
                for item in contents:
                    try:
                        if item.is_file():
                            item.unlink()
                        elif item.is_dir():
                            shutil.rmtree(item)
                    except Exception as e:
                        pass
                
                self.app.refresh_pak_lists()
            
        except Exception as e:
            pass
    
    def clear_appearance_selection(self):
        """清除外观文件夹（删除Panagway文件夹内的所有内容）"""
        try:
            if not self.app.panagway_dir.exists():
                return
            
            # 检查文件夹是否有内容
            contents = list(self.app.panagway_dir.iterdir())
            if not contents:
                return
            
            count = len(contents)
            result = messagebox.askyesno(
                self.app.texts.get("confirm_delete_title", "确认删除"), 
                self.app.texts.get("confirm_delete_appearance_message", "确定要删除Panagway文件夹中的 {count} 个pak文件吗？\n此操作不可撤销！").format(count=count)
            )
            
            if result:
                for item in contents:
                    try:
                        if item.is_file():
                            item.unlink()
                        elif item.is_dir():
                            shutil.rmtree(item)
                    except Exception as e:
                        pass
                
                # 清除种族选择数据
                self.app.appearance_race_selections.clear()
                self.app.appearance_race_widgets.clear()
                self.app.appearance_vanilla_races.clear()
                
                self.app.refresh_pak_lists()
            
        except Exception as e:
             pass

    def show_error_message(self, title, message):
        """显示错误消息"""
        messagebox.showerror(title, message)
    
    def show_info_message(self, title, message):
        """显示信息消息"""
        messagebox.showinfo(title, message)
    
    def show_warning_message(self, title, message):
        """显示警告消息"""
        messagebox.showwarning(title, message)

    def update_race_listbox(self):
        """更新种族列表框"""
        self.app.race_listbox.delete(0, tk.END)
        for pak in self.app.selected_race_paks:
            self.app.race_listbox.insert(tk.END, Path(pak).name)
    
    def update_appearance_listbox(self):
        """更新外观MOD显示区域"""
        # 清除现有的widget
        for widget in self.app.appearance_scroll_frame.winfo_children():
            widget.destroy()
        self.app.appearance_race_widgets.clear()
        
        # 为每个外观MOD创建显示项
        for i, pak_path in enumerate(self.app.selected_appearance_paks):
            pak_name = Path(pak_path).name
            
            # 创建每个MOD的框架
            mod_frame = ttk.Frame(self.app.appearance_scroll_frame)
            mod_frame.grid(row=i, column=0, sticky=(tk.W, tk.E), padx=5, pady=2)
            mod_frame.columnconfigure(1, weight=1)
            
            # MOD名称标签
            name_label = ttk.Label(mod_frame, text=pak_name, width=30)
            name_label.grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
            
            # 检查是否包含原版种族UUID
            has_vanilla_races = self.app.check_appearance_has_vanilla_races(pak_path)
            
            if has_vanilla_races:
                # 种族选择下拉菜单
                race_var = tk.StringVar()
                race_combobox = ttk.Combobox(mod_frame, textvariable=race_var, state="readonly", width=25)
                
                # 获取该MOD中实际包含的种族选项
                race_options = self.app.get_mod_race_options(pak_path)
                race_combobox['values'] = [option[0] for option in race_options]  # 显示名称
                
                # 绑定选择变化事件
                race_combobox.bind('<<ComboboxSelected>>', 
                                 lambda e, path=pak_path, cb=race_combobox: self.app.on_race_selection_changed(path, cb))
                
                race_combobox.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 10))
                
                # 设置默认选择（使用更长的延迟确保UI完全准备好）
                self.app.root.after(10, lambda cb=race_combobox, path=pak_path, options=race_options: self.app._set_combobox_default_value(cb, path, options))
                
                # 存储widget引用
                self.app.appearance_race_widgets[pak_path] = {
                    "frame": mod_frame,
                    "combobox": race_combobox
                }
            else:
                # 没有原版种族就提示
                info_label = ttk.Label(mod_frame, text="(无需种族选择)", foreground="gray")
                info_label.grid(row=0, column=1, sticky=tk.W, padx=(0, 10))
                
                # 存储widget引用
                self.app.appearance_race_widgets[pak_path] = {
                    "frame": mod_frame,
                    "combobox": None
                }
            
            # 删除按钮
            delete_button = ttk.Button(mod_frame, text="删除", width=8,
                                     command=lambda path=pak_path: self.app.delete_appearance_file_by_path(path))
            delete_button.grid(row=0, column=2, padx=(10, 0))
        
        # 更新滚动区域
        self.app.appearance_scroll_frame.update_idletasks()
        self.app.appearance_canvas.configure(scrollregion=self.app.appearance_canvas.bbox("all"))
    
    def show_race_context_menu(self, event):
        """显示种族列表框右键菜单"""
        try:
            # 获取点击位置的项目索引
            index = self.app.race_listbox.nearest(event.y)
            if index < self.app.race_listbox.size():
                # 选中该项目
                self.app.race_listbox.selection_clear(0, tk.END)
                self.app.race_listbox.selection_set(index)
                
                # 创建右键菜单
                context_menu = tk.Menu(self.app.root, tearoff=0)
                context_menu.add_command(label=self.app.texts.get("delete_file", "删除文件"), 
                                       command=lambda: self.app.delete_race_file(index))
                
                # 显示菜单
                context_menu.tk_popup(event.x_root, event.y_root)
        except Exception as e:
            pass
    
    def show_appearance_context_menu(self, event):
        """显示外观列表框右键菜单"""
        try:
            # 获取点击位置的项目索引
            index = self.app.appearance_listbox.nearest(event.y)
            if index < self.app.appearance_listbox.size():
                # 选中该项目
                self.app.appearance_listbox.selection_clear(0, tk.END)
                self.app.appearance_listbox.selection_set(index)
                
                # 创建右键菜单
                context_menu = tk.Menu(self.app.root, tearoff=0)
                context_menu.add_command(label=self.app.texts.get("delete_file", "删除文件"), 
                                       command=lambda: self.app.delete_appearance_file(index))
                
                # 显示菜单
                context_menu.tk_popup(event.x_root, event.y_root)
        except Exception as e:
            pass
    
    def show_sponsor_dialog(self):
        """显示赞助图片弹窗"""
        try:
            from PIL import Image, ImageTk
            
            # 创建弹窗
            dialog = tk.Toplevel(self.app.root)
            dialog.title("支持作者")
            dialog.resizable(False, False)
            dialog.transient(self.app.root)
            dialog.grab_set()
            
            # 加载并显示图片
            # exe中资源在临时目录
            if getattr(sys, 'frozen', False):
                # 打包后的exe环境
                sponsor_image_path = Path(sys._MEIPASS) / "sponsor.jpg"
            else:
                # 开发环境
                sponsor_image_path = Path(self.app.get_application_path()) / "src" / "asset" / "image" / "sponsor.jpg"
            if sponsor_image_path.exists():
                image = Image.open(sponsor_image_path)
                # 调整图片大小以适应弹窗
                image = image.resize((400, 250), Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(image)
                
                image_label = ttk.Label(dialog, image=photo)
                image_label.image = photo  # 保持引用
                image_label.pack(padx=20, pady=20)
            else:
                # 图片不存在就显示文字
                text_label = ttk.Label(dialog, text="感谢您的支持！\n如果您觉得这个工具有用，\n请考虑支持作者的开发工作。", 
                                     font=('Arial', 12), justify='center')
                text_label.pack(padx=40, pady=40)
            
            # 按钮区域
            button_frame = ttk.Frame(dialog)
            button_frame.pack(pady=(0, 20))
            
            # 我已支持按钮
            supported_button = ttk.Button(button_frame, text="我已支持", 
                                        command=dialog.destroy,
                                        style='Accent.TButton')
            supported_button.pack(side=tk.LEFT, padx=(0, 10))
            
            # 取消按钮
            cancel_button = ttk.Button(button_frame, text="取消", 
                                     command=dialog.destroy)
            cancel_button.pack(side=tk.LEFT)
            
            # 居中显示弹窗
            dialog.update_idletasks()
            x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
            y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
            dialog.geometry(f"+{x}+{y}")
            
        except ImportError:
            # PIL不可用就简单提示
            messagebox.showinfo("支持作者", "感谢您的支持！\n如果您觉得这个工具有用，请考虑支持作者的开发工作。")
        except Exception as e:
            messagebox.showerror("错误", f"显示支持信息时出错: {str(e)}")
    
    def center_window(self):
        """居中显示窗口"""
        self.app.root.update_idletasks()
        
        # 获取屏幕尺寸
        screen_width = self.app.root.winfo_screenwidth()
        screen_height = self.app.root.winfo_screenheight()
        
        # 获取窗口尺寸
        window_width = self.app.root.winfo_width()
        window_height = self.app.root.winfo_height()
        
        # 计算居中位置
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        
        # 设置窗口位置
        self.app.root.geometry(f"{window_width}x{window_height}+{x}+{y}")