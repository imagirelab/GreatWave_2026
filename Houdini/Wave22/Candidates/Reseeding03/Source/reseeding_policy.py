"""OFF診断の段階規則。警報で終点を選ばず、元の安全保護だけを早期停止へ使う。"""


def next_decision(sample, initial_pair_matched, field_valid, safety_passed,
                  previous_coverage_alert, current_coverage_alarm, static_gate_passed=None):
    assert isinstance(sample, int) and 0 <= sample <= 360
    alert = bool(previous_coverage_alert or current_coverage_alarm)
    if not initial_pair_matched:
        action = 'STOP_INITIAL_PAIR_MISMATCH'
    elif not field_valid:
        action = 'STOP_INVALID_FIELD'
    elif not safety_passed:
        action = 'STOP_ORIGINAL_SAFETY_GUARD'
    elif sample == 360:
        assert isinstance(static_gate_passed, bool)
        action = 'FINISH_STATIC_DIAGNOSTIC'
    else:
        action = 'CONTINUE_TO_FIXED_ENDPOINT'
    return {'action': action, 'coverage_alert_latched': alert,
            'static_gate_passed': static_gate_passed,
            'drive_authorized': False, 'physical_improvement_verified': False,
            'next_sample': sample+1 if action == 'CONTINUE_TO_FIXED_ENDPOINT' else None}
