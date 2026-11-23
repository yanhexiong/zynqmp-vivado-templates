# 可配置 Vivado / Vitis 工程模板（Zynq UltraScale+ MPSoC）

面向 **FZ5C / FZ5D** 与 **AXU4EV-F** 的跨平台（Windows / Linux）可配置硬件模板与裸机外设诊断套件：

- **图形化/命令行硬件裁剪**：基于 Kconfig + Textual 的蓝底全屏配置界面（支持中/英/双语），可裁剪 PS 外设、调节 `pl_clk0` 与 PL 共享 DDR 容量。
- **纯 Tcl 工程初始化**：Python 只负责编辑并校验配置，Vivado Tcl 读取生成的 `config.tcl` 搭建工程与 Block Design。
- **配套 Vitis 诊断工程**：提供一键编译、生成 `BOOT.BIN`、JTAG 下载及跨平台串口自动抓包/判读。

---

## 支持的开发板与文档导航

| 开发板 | 器件型号 | Vivado 模板与硬件说明 | Vitis 外设诊断 | 硬件验证记录 |
|---|---|---|---|---|
| **EdgeBoard FZ5C / FZ5D** | `xczu5ev-sfvc784-1-i`（可选 `-2`） | [fz5_template](fz5_template/README.md) | [fz5_vitis](fz5_vitis/README.md) | [VALIDATION](fz5_template/docs/VALIDATION.md) |
| **AXU4EV-F** | `xczu4ev-sfvc784-2-i` | [axu4ev_template](axu4ev_template/README.md) | [axu4ev_vitis](axu4ev_vitis/README.md) | [VALIDATION](axu4ev_template/docs/VALIDATION.md) |

### 仓库结构

```text
.
├── scripts/
│   ├── zynqmp.py              # 根目录统一 CLI（配置 / Vivado / Vitis / JTAG / 串口）
│   ├── zynqmp_host.py         # 跨平台工具链发现与调用（Windows / Linux）
│   └── zynqmp_serial.py       # 跨平台串口抓包与 JTAG 下载共享逻辑
├── fz5_template/              # FZ5C / FZ5D Vivado 工程模板与配置器
├── fz5_vitis/                 # FZ5 Vitis 裸机诊断工程
├── axu4ev_template/           # AXU4EV-F Vivado 工程模板与配置器
├── axu4ev_vitis/              # AXU4EV-F Vitis 裸机诊断工程
└── tests/                     # 跨平台工具链发现与 Tcl 契约测试
```

---

## 环境要求

1. **Python 3.10+** 与 **[uv](https://docs.astral.sh/uv/)**（推荐用 `uv` 自动管理配置界面的虚拟环境与串口测试依赖；无需安装 Make 或 MinGW）。
2. **AMD / Xilinx Vivado 与 Vitis**（仅在生成工程、综合或编译软件时需要）：
   - **基线验证版本**：**Vivado / Vitis 2023.1**（`Vitis` 需包含经典 `xsct` 与 `bootgen`）。
   - **其他版本**：支持通过 `--tool-version`、安装目录参数或环境变量切换本机其他已安装版本。

---

## 快速上手（Windows / Linux 通用）

以下所有命令均在**仓库根目录**执行（将 `<board>` 替换为 `fz5` 或 `axu4ev`）：

### 第 0 步：查看本机可用 Vivado / Vitis 版本（可选）

```bash
python3 scripts/zynqmp.py toolchains
```

会扫描标准安装路径、`PATH` 及 `XILINX_VIVADO` / `XILINX_VITIS`，列出本机已安装版本及是否带有 `xsct` / `bootgen`。

### 第 1 步：配置硬件参数（如使用默认配置可跳过）

启动蓝底全屏配置界面（首次运行会自动由 `uv` 创建虚拟环境）：

```bash
uv run --project fz5_template fz5-config --lang zh
# 或
uv run --project axu4ev_template axu4ev-config --lang zh
```

- 常用键位：`↑`/`↓` 选择、`Enter` 进入/改值、`空格` 开关、`F2` 保存、`F3` 加载预设、`F4` 切换中/英/双语（`--lang en` / `--lang both`）、`/` 搜索、`F1` 帮助、`F10` 退出。详见各模板的 `docs/UI.md`。
- 也可通过命令行修改，例如：`uv run --project fz5_template fz5-config set PL_RESERVED_MB=2048 PS_USB0=n`。

### 第 2 步：创建 Vivado 工程并导出 `.bit` / `.xsa`

> **提示**：仓库中 `fz5_template/export/` 与 `axu4ev_template/export/` 已预置默认配置编译好的 `.bit` 与 `.xsa`。若暂不修改硬件配置，可直接跳到**第 3 步**。

```bash
# 只生成 Vivado 工程与 Block Design（输出在 <board>_template/build/<CONFIG_ID前12位>/）
python3 scripts/zynqmp.py vivado fz5 project

# 完整综合、布局布线、生成 bitstream 并发布到 <board>_template/export/
python3 scripts/zynqmp.py vivado fz5 bitstream
```

也可以在 Vivado GUI 的 Tcl Console 中手动初始化当前目录的工程：

```tcl
source {fz5_template/tcl/init_project.tcl}
# 或
source {axu4ev_template/tcl/init_project.tcl}
```

### 第 3 步：编译 Vitis 诊断程序并生成 `BOOT.BIN`

```bash
# 创建/更新 Vitis 工作区并编译诊断 ELF
python3 scripts/zynqmp.py vitis fz5 build

# 打包 SD 卡启动镜像 BOOT.BIN（含 FSBL + PMUFW + bitstream + ELF）
python3 scripts/zynqmp.py vitis fz5 boot
```

- 构建产物位于 `<board>_vitis/build/<CONFIG_ID前12位>/`。
- 若只调整软件诊断开关（不改硬件外设/内存），编辑对应 `<board>_vitis/src/test_options.h` 后直接重跑本步即可，**无需重跑 Vivado**。

### 第 4 步：上板运行与串口自动抓包

```bash
# 方式一：SD 卡启动（先开启串口监听再上电；Windows 填 COMx，Linux 填 /dev/ttyUSB0）
python3 scripts/zynqmp.py serial fz5 -- --console COM7

# 方式二：JTAG 在线下载并采集串口（需先接好 JTAG 并启动 hw_server）
python3 scripts/zynqmp.py serial fz5 -- --console COM7 --jtag
```

---

## 多版本工具链切换

| 方式 | 示例 | 说明 |
|---|---|---|
| 指定版本号 | `python3 scripts/zynqmp.py vivado fz5 project --tool-version 2024.1` | 从 `toolchains` 扫描到的版本中选择对应版本 |
| 指定安装目录 | `python3 scripts/zynqmp.py vitis axu4ev build --vitis-dir /opt/Xilinx/Vitis/2023.2` | 直接指定 `Vivado` 或 `Vitis` 安装根目录 |
| 环境变量 | 设置 `XILINX_VIVADO` / `XILINX_VITIS` 或 `ZYNQMP_VIVADO_VERSION` | 适合在已 `source settings64.sh` 的终端中使用 |
| 严格锁定 2023.1 | 传入 `--strict-version` 或设置 `ZYNQMP_STRICT_VERSION=1` | 默认允许其他 Vivado 版本继续构建并自动兼容匹配 IP；开启后版本非 `2023.1` 即报错 |

各子目录下也保留了独立脚本（如 `fz5_template/scripts/fz5.py`、`axu4ev_template/scripts/axu4ev.py`、`*_vitis/scripts/build.py` 与 `serial_test.py`）以及 Windows PowerShell 兼容包装（`*.ps1`），具体参数见各自 README。

---

## 运行自动化测试

```bash
# 跨平台工具链发现与 Tcl 契约测试
python3 -m unittest discover -s tests -v

# 配置器、TUI 与 Tcl 交接测试
uv run --project fz5_template python -m unittest discover -s fz5_template/tests -v
uv run --project axu4ev_template python -m unittest discover -s axu4ev_template/tests -v

# 串口报告解析测试（自动拉取 pyserial）
uv run --with pyserial python -m unittest discover -s fz5_vitis/tests -v
uv run --with pyserial python -m unittest discover -s axu4ev_vitis/tests -v
```

---

## 设计边界与注意事项

- **PS / PL 共享内存**：两款开发板均只有 PS 侧 DDR4，没有独立 PL DDR。配置中的 `PL_RESERVED_MB` 是从 PS 高端 DDR 末尾划出的软件约定池，低端 DDR 与高端 DDR 之间存在地址空洞；Linux 设备树请合并生成的 `*-memory.dtsi`（带 `no-map`）。详情见各模板 README。
- **构建与实机记录分离**：`docs/VALIDATION.md` 记录工具构建结果与上板验收情况；生成 `.bit` / `.elf` / `BOOT.BIN` 成功不代表跳过外设实机验收。
