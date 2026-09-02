# version: 1.0

from wm_launch import _build_restart_command, _is_wm_restart_handoff


def test_restart_handoff_accepts_python_path_with_spaces():
    python_exe = r"C:\Program Files\Python313\python.exe"
    start_script = r"C:\Warsztat-Menager\start.py"
    args = [python_exe, start_script]

    assert _is_wm_restart_handoff(
        python_exe,
        args,
        env={"WM_RESTARTED_AFTER_UPDATE": "1"},
        os_name="nt",
        executable=python_exe,
    )

    command = _build_restart_command(python_exe, args)
    assert command == [python_exe, start_script]
    assert command[0] == r"C:\Program Files\Python313\python.exe"


def test_restart_handoff_requires_update_marker():
    python_exe = r"C:\Program Files\Python313\python.exe"
    args = [python_exe, r"C:\Warsztat-Menager\start.py"]

    assert not _is_wm_restart_handoff(
        python_exe,
        args,
        env={},
        os_name="nt",
        executable=python_exe,
    )


def test_restart_handoff_does_not_intercept_other_programs():
    python_exe = r"C:\Program Files\Python313\python.exe"
    args = [python_exe, r"C:\Warsztat-Menager\other_script.py"]

    assert not _is_wm_restart_handoff(
        python_exe,
        args,
        env={"WM_RESTARTED_AFTER_UPDATE": "1"},
        os_name="nt",
        executable=python_exe,
    )
