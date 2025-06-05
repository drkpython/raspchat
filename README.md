raspberrypi llm chat for Hildy 项目安装与运行指南
## 经典更新
首先更新系统软件包：
```bash
sudo apt update
sudo apt upgrade -y
```
安装工具和环境：
```bash
sudo apt install git python3 python3-venv python3-pip
```
## 克隆代码仓库：
```bash
git clone https://github.com/drkpython/raspchat.git
```
## 创建虚拟环境
进入仓库文件夹：
```bash
cd raspchat
```
创建 Python 虚拟环境：
```bash
python3 -m venv venv
```
激活虚拟环境
```bash
source venv/bin/activate
```
## 装依赖
```bash
pip install -r requirements.txt
```
## 运行
在虚拟环境激活且位于项目目录的状态下，运行主程序：
```bash
python raspchat.py
```
## 按空格跟它说话

## 结束工作
当你完成项目工作后，可通过以下命令退出虚拟环境：
```bash
deactivate
```
