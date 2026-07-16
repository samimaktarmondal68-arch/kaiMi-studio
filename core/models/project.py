from dataclasses import dataclass


@dataclass
class Project:

    name: str

    topic: str

    language: str

    style: str

    created: str

    status: str = "Research"