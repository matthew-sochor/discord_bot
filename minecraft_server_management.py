# bot.py
import os
from pathlib import Path
import discord
import yaml
from typing import Dict, Tuple
import boto3
from collections import defaultdict
import subprocess
import time

with open(".secrets.yaml", "r") as fp:
    env = yaml.load(fp, Loader=yaml.FullLoader)

TOKEN = env["discord_token"]

client = discord.Client()


def get_server_info(state: str = "running"):
    ec2 = boto3.resource("ec2")

    # Get information for all running instances
    running_instances = ec2.instances.filter(
        Filters=[{"Name": "instance-state-name", "Values": [state]}]
    )

    for instance in running_instances:
        for tag in instance.tags:
            if "Name" in tag["Key"]:
                name = tag["Value"]
                if name == "Minecraft":
                    return instance

    return None


def start_server() -> str:
    instance = get_server_info("stopped")
    ec2_client = boto3.client("ec2")
    if instance is not None:

        with open(f"instance.yaml", "r") as fp:
            instance = yaml.load(fp, Loader=yaml.FullLoader)
        _ = ec2_client.start_instances(InstanceIds=[instance["id"]])
        instance = get_server_info()
        while instance.state["Name"] != "running":
            print(f"Instance not ready yet, in state: {instance.state['Name']}")
            time.sleep(5)
            instance = get_server_info()

        start_server = [
            "ssh",
            "-o",
            "StrictHostKeyChecking=no",
            "-i",
            "~/.ssh/minecraft.pem",
            f"ubuntu@{instance.public_ip_address}",
            "-t",
            "/home/ubuntu/tmux_launch.sh",
        ]
        _ = subprocess.run(start_server)
        client = boto3.client("route53")
        client.change_resource_record_sets(
            HostedZoneId="/hostedzone/Z1M5NV8QVFQX3A",
            ChangeBatch={
                "Changes": [
                    {
                        "Action": "UPSERT",
                        "ResourceRecordSet": {
                            "Name": "mc.mattso.ch",
                            "Type": "A",
                            "TTL": 300,
                            "ResourceRecords": [{"Value": instance.public_ip_address}],
                        },
                    }
                ]
            },
        )
        return "Server has been started"
    else:
        return "Minecraft server is already running"


def stop_server() -> str:
    instance = get_server_info()
    ec2_client = boto3.client("ec2")
    if instance is not None:
        _ = ec2_client.stop_instances(InstanceIds=[instance.id])
        out = {"id": instance.id}

        with open(f"instance.yaml", "w") as fp:
            yaml.dump(out, fp)
        return "Server has been stopped"
    else:
        return "Minecraft server was not found, no actions taken"


def update_server() -> str:
    return "server is doin sumthin"


def get_server_status() -> str:
    instance = get_server_info()
    if instance is not None:
        reply = (
            f"Server information:\n"
            + f"Type: {instance.instance_type},\n"
            + f"State: {instance.state['Name']},\n"
            + f"Private IP: {instance.private_ip_address},\n"
            + f"Public IP: {instance.public_ip_address},\n"
            + f"Launch time: {instance.id}"
        )
        return reply
    else:
        return "Minecraft server was not found"


def add_ip() -> str:
    return "server is updated"


@client.event
async def on_ready():
    print(f"We have logged in as {client.user}")


@client.event
async def on_message(message: discord.message.Message) -> None:

    if message.author == client.user:
        return

    if message.content.lower().startswith("!mc") or isinstance(
        message.channel, discord.channel.DMChannel
    ):
        if message.content.lower() == "!mc status":
            reply = get_server_status()
        elif message.content.lower() == "!mc start":
            reply = start_server()
        elif message.content.lower() == "!mc stop":
            reply = stop_server()
        elif message.content.lower() == "!mc add_ip":
            reply = add_ip()
        else:
            reply = "To use !mc stop|start|update|status|add_ip|help"
        await message.channel.send(reply)


client.run(TOKEN)
