# 首次访问门自检失败与修复

首次GitHub网络clone和两个新CPU依赖环境安装成功。固定commit为789da788f504400451b388ec30eae24241e31626。
首次访问门probe失败：系统/usr/lib/python3.12/sitecustomize.py先于venv sitecustomize.py被导入，自定义hook未激活。
该probe读取了一次旧main/README.md后报告ACCESS_GUARD_NOT_ACTIVE；当时尚未开始任何scorer、模型或RL-B科学验证。
这次运行不算独立验收PASS；原目录、环境和失败日志保留，没有删除或覆盖证据。

修复只涉及测试隔离层：install_access_guard.py在新venv通过独立.pth import唯一模块，绕开系统同名模块遮蔽。
probe先确认唯一模块已加载，再尝试必须被拒绝的旧根访问；新增child-venv单测。
修复后的完整验收另用全新GitHub网络clone目录、全新两个Python3.12环境重新开始，不借用第一次克隆或环境。
原科学代码、合同、fixture和阈值不变。
