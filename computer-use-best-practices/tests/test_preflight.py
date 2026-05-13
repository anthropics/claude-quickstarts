from computer_use import preflight


def test_checks_return_bool():
    assert isinstance(preflight.screen_recording_granted(), bool)
    assert isinstance(preflight.accessibility_granted(), bool)


def test_check_and_warn_non_required_never_exits():
    assert isinstance(preflight.check_and_warn(require=False), bool)
