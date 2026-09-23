# Runtime license information

The packaged application includes PySide6 Essentials, Shiboken6, and Qt 6
runtime libraries. The installed Python wheels declare the licensing choice as
`LicenseRef-Qt-Commercial OR LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only`.

This project uses them under the LGPL option. License and compliance details:

- `LGPL-3.0.txt`: GNU Lesser General Public License version 3
- `GPL-3.0.txt`: GNU General Public License version 3, incorporated by LGPLv3
- Qt licensing: https://www.qt.io/licensing/open-source-lgpl-obligations
- Qt source availability: https://download.qt.io/official_releases/qt/
- PySide source: https://code.qt.io/cgit/pyside/pyside-setup.git/

The PyInstaller `onedir` layout keeps the Qt dynamic libraries separate and
replaceable rather than statically linking them into the application.

