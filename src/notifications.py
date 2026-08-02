import os
import subprocess
import sys

from rich.console import Console

import config

console = Console()


def notify(message: str, urgency: str = "normal") -> None:
    """
    Alert the operator. Always prints to console.
    Fires a desktop notification when DESKTOP_NOTIFY=1 (local/cron deployments).
    Also publishes to SNS when SNS_TOPIC_ARN is configured (Lambda deployments).
    boto3 is not a declared dependency — it is available in the Lambda runtime
    and imported lazily so local runs without boto3 installed are unaffected.
    """
    console.print(f"[bold yellow]Alert:[/bold yellow] {message}")
    _desktop_notify(message, urgency)
    if not config.SNS_TOPIC_ARN:
        return
    try:
        import boto3

        boto3.client("sns", region_name=config.AWS_REGION).publish(
            TopicArn=config.SNS_TOPIC_ARN,
            Subject="job-matcher alert",
            Message=message,
        )
    except Exception as e:
        console.print(f"[red]Failed to send SNS notification:[/red] {e}")


def _desktop_notify(message: str, urgency: str) -> None:
    if not config.DESKTOP_NOTIFY or sys.stdout.isatty():
        return
    try:
        env = os.environ.copy()
        uid = os.getuid()
        env.setdefault("DISPLAY", ":0")
        env.setdefault("DBUS_SESSION_BUS_ADDRESS", f"unix:path=/run/user/{uid}/bus")
        icon = "dialog-error" if urgency == "critical" else "dialog-information"
        subprocess.run(
            [
                "notify-send",
                "--app-name=job-matcher",
                f"--urgency={urgency}",
                f"--icon={icon}",
                "job-matcher",
                message,
            ],
            env=env,
            timeout=5,
            capture_output=True,
        )
    except Exception:
        pass
