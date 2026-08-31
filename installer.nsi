; ============================================================
; NSIS 安装器脚本 - 装箱打印系统
;
; 设计：
;   1. NSIS 编译期宏展开使用 ANSI 路径，所以所有 File 引用都用 ASCII 名
;   2. 安装器显示给用户的中文用 Unicode 模式处理
;   3. 实际安装目录使用中文 APP_NAME（在 Unicode 模式下正常显示）
; 用法（build.bat 调用）：
;     makensis /DAPP_VERSION=1.0.0 installer.nsi
; ============================================================

Unicode true

!include "MUI2.nsh"
!include "LogicLib.nsh"

; ---------------- 宏定义（APP_VERSION 由命令行 /D 传入） ----------------
!ifndef APP_VERSION
  !define APP_VERSION "0.0.0"
!endif

; 中文显示名（运行时显示给用户）
!define APP_DISPLAY_NAME "装箱打印系统"
!define APP_PUBLISHER "装箱打印工具团队"

; ASCII 内部名（编译器引用文件 / 安装目录时用，避免 ANSI 路径问题）
!define APP_NAME_ASCII "PackingPrintSystem"
!define APP_SOURCE_EXE "PackingPrint_v${APP_VERSION}_portable.exe"
!define APP_INSTALLED_EXE "装箱打印系统.exe"
!define APP_SETUP_OUT "PackingPrintSystem_v${APP_VERSION}_setup.exe"

InstallDir "$LOCALAPPDATA\${APP_DISPLAY_NAME}"
; 备用方案：一些 Windows 容器/沙箱下 $LOCALAPPDATA 解析异常（被重定向到 D: 盘），
; 用户可改用下面这行把装到用户家目录的固定位置：
; InstallDir "$DOCUMENTS\${APP_DISPLAY_NAME}"
InstallDirRegKey HKCU "Software\${APP_NAME_ASCII}" ""

; 在 .onInit 里通过 Win32 API 强制解析当前用户的 LocalAppData，
; 避免 $LOCALAPPDATA 在沙箱/容器环境下被改写到 D:\ 等异常位置
Function .onInit
  ; CSIDL_LOCAL_APPDATA = 28
  SetShellVarContext current
  System::Call 'Shell32::SHGetFolderPath(i $0, i 28, i 0, i 0, t .r1)'
  StrCpy $INSTDIR "$1\${APP_DISPLAY_NAME}"
FunctionEnd

RequestExecutionLevel user

; ---------------- 现代 UI ----------------
!define MUI_ABORTWARNING
!define MUI_ICON "icon.ico"
!define MUI_UNICON "icon.ico"

!define MUI_WELCOMEPAGE_TITLE "${APP_DISPLAY_NAME} 安装向导"
!define MUI_WELCOMEPAGE_TEXT "本安装程序将引导您完成 ${APP_DISPLAY_NAME} 的安装。$\r$\n$\r$\n版本：${APP_VERSION}$\r$\n$\r$\n点击下一步继续。"
!define MUI_FINISHPAGE_TITLE "${APP_DISPLAY_NAME} 安装完成"
!define MUI_FINISHPAGE_TEXT "${APP_DISPLAY_NAME} 已安装到您的电脑。$\r$\n$\r$\n点击完成关闭本向导。"
!define MUI_FINISHPAGE_RUN "$INSTDIR\${APP_INSTALLED_EXE}"
!define MUI_FINISHPAGE_RUN_TEXT "启动 ${APP_DISPLAY_NAME}"
!define MUI_FINISHPAGE_SHOWREADME "$INSTDIR\README.txt"
!define MUI_FINISHPAGE_SHOWREADME_TEXT "打开自述文件"
!define MUI_FINISHPAGE_SHOWREADME_NOTCHECKED

; ---------------- 版本信息（右键安装器属性可见） ----------------
VIProductVersion "${APP_VERSION}.0"
VIAddVersionKey "ProductName" "${APP_DISPLAY_NAME}"
VIAddVersionKey "LegalCopyright" "© ${APP_PUBLISHER}"
VIAddVersionKey "FileDescription" "${APP_DISPLAY_NAME} 安装程序"
VIAddVersionKey "FileVersion" "${APP_VERSION}"
VIAddVersionKey "ProductVersion" "${APP_VERSION}"
VIAddVersionKey "CompanyName" "${APP_PUBLISHER}"

Name "${APP_DISPLAY_NAME} ${APP_VERSION}"
OutFile "${APP_SETUP_OUT}"
BrandingText "${APP_DISPLAY_NAME} ${APP_VERSION}"

; ---------------- 安装节 ----------------
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "LICENSE.txt"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_WELCOME
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_UNPAGE_FINISH

!insertmacro MUI_LANGUAGE "SimpChinese"

Section "主程序（必需）" SEC_MAIN
  SectionIn RO

  ; 强制使用当前用户的 shell 变量（避免 admin 提升后 $LOCALAPPDATA 指向 system）
  SetShellVarContext current
  SetOutPath "$INSTDIR"

  ; EXE 主程序（从 ASCII 源文件复制，安装时重命名为中文文件名）
  File "${APP_SOURCE_EXE}"
  Rename "$INSTDIR\${APP_SOURCE_EXE}" "$INSTDIR\${APP_INSTALLED_EXE}"

  ; 资源
  File "packing_label.css"
  File "LICENSE.txt"
  File "README.txt"

  ; 写入 version.json（updater 用它判断当前版本）
  FileOpen $0 "$INSTDIR\version.json" w
  FileWrite $0 '{\n  "version": "${APP_VERSION}"$\n}\n'
  FileClose $0

  ; 写入注册表（HKCU\Software\<ASCII 名>，避免 ANSI 路径问题）
  WriteRegStr HKCU "Software\${APP_NAME_ASCII}" "" $INSTDIR
  WriteRegStr HKCU "Software\${APP_NAME_ASCII}" "Version" "${APP_VERSION}"
  WriteRegStr HKCU "Software\${APP_NAME_ASCII}" "Publisher" "${APP_PUBLISHER}"
  WriteRegStr HKCU "Software\${APP_NAME_ASCII}" "DisplayName" "${APP_DISPLAY_NAME}"

  ; 卸载信息
  WriteUninstaller "$INSTDIR\Uninstall.exe"

  ; 开始菜单
  CreateDirectory "$SMPROGRAMS\${APP_DISPLAY_NAME}"
  CreateShortcut "$SMPROGRAMS\${APP_DISPLAY_NAME}\${APP_DISPLAY_NAME}.lnk" "$INSTDIR\${APP_INSTALLED_EXE}"
  CreateShortcut "$SMPROGRAMS\${APP_DISPLAY_NAME}\卸载 ${APP_DISPLAY_NAME}.lnk" "$INSTDIR\Uninstall.exe"

  ; 桌面快捷方式
  CreateShortcut "$DESKTOP\${APP_DISPLAY_NAME}.lnk" "$INSTDIR\${APP_INSTALLED_EXE}"
SectionEnd

; ---------------- 卸载节 ----------------
Section "Uninstall"
  SetShellVarContext current

  ; 删文件
  Delete "$INSTDIR\${APP_INSTALLED_EXE}"
  Delete "$INSTDIR\packing_label.css"
  Delete "$INSTDIR\LICENSE.txt"
  Delete "$INSTDIR\README.txt"
  Delete "$INSTDIR\version.json"
  Delete "$INSTDIR\Uninstall.exe"

  ; 尝试删除目录（仅当空）
  RMDir "$INSTDIR"

  ; 删快捷方式
  Delete "$SMPROGRAMS\${APP_DISPLAY_NAME}\${APP_DISPLAY_NAME}.lnk"
  Delete "$SMPROGRAMS\${APP_DISPLAY_NAME}\卸载 ${APP_DISPLAY_NAME}.lnk"
  RMDir "$SMPROGRAMS\${APP_DISPLAY_NAME}"
  Delete "$DESKTOP\${APP_DISPLAY_NAME}.lnk"

  ; 删注册表
  DeleteRegKey HKCU "Software\${APP_NAME_ASCII}"
SectionEnd

; ---------------- 描述（左侧面板） ----------------
LangString DESC_SEC_MAIN ${LANG_SIMPCH} "${APP_DISPLAY_NAME} 主程序及运行依赖。"
!insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
  !insertmacro MUI_DESCRIPTION_TEXT ${SEC_MAIN} $(DESC_SEC_MAIN)
!insertmacro MUI_FUNCTION_DESCRIPTION_END