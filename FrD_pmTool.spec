# -*- mode: python -*-

block_cipher = None


a = Analysis(['FrD_pmTool.py'],
             pathex=['D:\\_PROJECT\\GIT\\FrD_pmTool'],
             binaries=None,
             datas=[
                ('D:\\_PROJECT\\GIT\\FrD_pmTool\\FrD_pmTool.ui', '.'),
                ('D:\\_PROJECT\\GIT\\FrD_pmTool\\cacerts.txt', '.'),
                ('D:\\_PROJECT\\GIT\\FrD_pmTool\\FrD_pmTool.ico', '.')
             ],
             hiddenimports=[],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          exclude_binaries=True,
          name='FrD_pmTool',
          debug=False,
          strip=False,
          upx=True,
          console=True, icon='FrD_pmTool.ico')
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               name='FrD_pmTool')
