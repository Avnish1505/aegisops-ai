"""Validate the deployment safety gate, then notify the team."""


def validate_deployment_safety_gate(build):
    if not build.get("tests_passed"):
        return False
    if not build.get("security_scan_clean"):
        return False
    return True


def notify_team(build):
    print(f"Build {build['id']} is ready")
    return True
