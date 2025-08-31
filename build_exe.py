#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BG3 MOD兼容性工具打包脚本
自动将项目打包成exe文件
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

def check_pyinstaller():
    """检查PyInstaller是否已安装"""
    try:
        import PyInstaller
        print("✓ PyInstaller已安装")
        return True
    except ImportError:
        print("✗ PyInstaller未安装")
        return False

def install_pyinstaller():
    """安装PyInstaller"""
    print("正在安装PyInstaller...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
        print("✓ PyInstaller安装成功")
        return True
    except subprocess.CalledProcessError:
        print("✗ PyInstaller安装失败")
        return False

def clean_build_dirs():
    """清理构建目录"""
    # 清理build和__pycache__目录
    dirs_to_clean = ['build', '__pycache__']
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            print(f"清理目录: {dir_name}")
            shutil.rmtree(dir_name)
    
    # 清理dist目录，但保留指定的子目录
    dist_dir = Path('dist')
    if dist_dir.exists():
        preserve_dirs = ['Output', 'Panagway', 'Sourcemod']
        
        # 遍历dist目录下的所有内容
        for item in dist_dir.iterdir():
            if item.name == 'Data':
                # 对于Data目录，需要特殊处理
                data_dir = item
                if data_dir.is_dir():
                    # 遍历Data目录下的内容
                    for data_item in data_dir.iterdir():
                        if data_item.name not in preserve_dirs:
                            # 删除不在保留列表中的目录或文件
                            if data_item.is_dir():
                                print(f"清理目录: Data\\{data_item.name}")
                                shutil.rmtree(data_item)
                            else:
                                print(f"删除文件: Data\\{data_item.name}")
                                data_item.unlink()
                        else:
                            print(f"保留目录: Data\\{data_item.name}")
            else:
                # 删除dist目录下的其他内容（除了Data目录）
                if item.is_dir():
                    print(f"清理目录: {item.name}")
                    shutil.rmtree(item)
                else:
                    print(f"删除文件: {item.name}")
                    item.unlink()
    
    # 清理.spec文件
    spec_files = list(Path('.').glob('*.spec'))
    for spec_file in spec_files:
        print(f"删除spec文件: {spec_file}")
        spec_file.unlink()

def create_build_command():
    """创建PyInstaller构建命令"""
    # 基础命令
    cmd = [
        'pyinstaller',
        '--onefile',  # 打包成单个exe文件
        '--windowed',  # 不显示控制台窗口
        '--name=BG3_Race_CC_Generator',  # exe文件名
    ]
    
    # 检查并添加图标（修复任务栏图标显示问题）
    icon_path = 'src/asset/image/打包图标.ico'
    if os.path.exists(icon_path):
        cmd.append(f'--icon={icon_path}')
        # 添加图标文件到打包资源
        cmd.append(f'--add-data={icon_path};src/asset/image')
        print(f"✓ 找到图标文件: {icon_path}")
    else:
        print(f"✗ 图标文件不存在: {icon_path}")
    
    # 移除None值
    cmd = [c for c in cmd if c is not None]
    
    # 添加数据文件
    data_files = [
        '--add-data=locales;locales',  # 国际化文件
        '--add-data=src;src',  # 源码模块
    ]
    
    # 检查并添加图标和图片资源
    if os.path.exists('src/asset'):
        data_files.append('--add-data=src/asset;src/asset')
    
    # 确保sponsor.jpg被正确打包
    sponsor_path = 'src/asset/image/sponsor.jpg'
    if os.path.exists(sponsor_path):
        # 添加到根目录和完整路径两个位置
        data_files.append(f'--add-data={sponsor_path};.')
        data_files.append(f'--add-data={sponsor_path};src/asset/image')
        print(f"✓ 找到sponsor图片: {sponsor_path}")
    else:
        print(f"✗ sponsor图片不存在: {sponsor_path}")
    
    cmd.extend(data_files)
    
    # 隐藏导入
    hidden_imports = [
        '--hidden-import=tkinter',
        '--hidden-import=tkinter.ttk',
        '--hidden-import=tkinter.filedialog',
        '--hidden-import=tkinter.messagebox',
        '--hidden-import=tkinter.scrolledtext',
        '--hidden-import=PIL',
        '--hidden-import=PIL.Image',
        '--hidden-import=PIL.ImageTk',
    ]
    
    cmd.extend(hidden_imports)
    
    # 排除不需要的模块
    excludes = [
        '--exclude-module=matplotlib',
        '--exclude-module=numpy',
        '--exclude-module=pandas',
        '--exclude-module=scipy',
    ]
    
    cmd.extend(excludes)
    
    # 主程序文件
    cmd.append('bg3_compatibility_generator.pyw')
    
    return cmd

def build_exe():
    """构建exe文件"""
    print("开始构建exe文件...")
    
    cmd = create_build_command()
    print(f"执行命令: {' '.join(cmd)}")
    
    try:
        subprocess.check_call(cmd)
        print("✓ exe文件构建成功")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ exe文件构建失败: {e}")
        return False

def copy_required_files():
    """复制必需的文件到dist目录"""
    dist_dir = Path('dist')
    if not dist_dir.exists():
        print("✗ dist目录不存在")
        return False
    
    print("复制必需文件...")
    
    # 只复制Data\Tools目录到dist
    source_tools_dir = Path('Data') / 'Tools'
    dest_data_dir = dist_dir / 'Data'
    dest_tools_dir = dest_data_dir / 'Tools'
    
    if source_tools_dir.exists():
        # 确保目标Data目录存在
        dest_data_dir.mkdir(exist_ok=True)
        
        # 删除已存在的Tools目录
        if dest_tools_dir.exists():
            shutil.rmtree(dest_tools_dir)
        
        # 复制Tools目录
        shutil.copytree(source_tools_dir, dest_tools_dir)
        print(f"✓ 复制Data\\Tools目录到dist")
    else:
        print("✗ 源Data\\Tools目录不存在")
        return False
    
    return True

def create_readme_for_dist():
    """为发布版本创建说明文件（已禁用）"""
    # 用户不需要README文件，跳过创建
    print("✓ 跳过创建说明文件（按用户要求）")

def main():
    """主函数"""
    print("=" * 50)
    print("BG3 MOD兼容性工具 - 打包脚本")
    print("=" * 50)
    
    # 检查当前目录
    if not os.path.exists('bg3_compatibility_generator.pyw'):
        print("✗ 错误：请在项目根目录运行此脚本")
        return False
    
    # 检查PyInstaller
    if not check_pyinstaller():
        if not install_pyinstaller():
            return False
    
    # 清理构建目录
    clean_build_dirs()
    
    # 构建exe
    if not build_exe():
        return False
    
    # 复制必需文件
    if not copy_required_files():
        return False
    
    # 创建发布说明
    create_readme_for_dist()
    
    print("\n" + "=" * 50)
    print("✓ 打包完成！")
    print(f"✓ exe文件位置: {Path('dist').absolute()}")
    print("✓ 可以将dist目录中的所有文件分发给用户")
    print("=" * 50)
    
    return True

if __name__ == '__main__':
    try:
        success = main()
        if not success:
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n用户取消操作")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ 发生错误: {e}")
        sys.exit(1)