from rich.console import Console

import config

console = Console()


def notify(message: str) -> None:
    """
    Alert the operator. Always prints to console.
    Also publishes to SNS when SNS_TOPIC_ARN is configured (Lambda deployments).
    boto3 is not a declared dependency — it is available in the Lambda runtime
    and imported lazily so local runs without boto3 installed are unaffected.
    """
    console.print(f"[bold yellow]Alert:[/bold yellow] {message}")
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
