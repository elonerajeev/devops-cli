from typing import List, Optional, Dict, Any
from pydantic import BaseModel, HttpUrl, Field, validator
import re

class HealthCheckSchema(BaseModel):
    type: str
    url: Optional[HttpUrl] = None
    expected_status: Optional[int] = None
    host: Optional[str] = None
    port: Optional[int] = None
    command: Optional[str] = None

    @validator('url', pre=True)
    def convert_url_to_str(cls, v):
        if isinstance(v, HttpUrl):
            return str(v)
        return v

    @validator('port')
    def validate_port(cls, v, values):
        if v is not None and not (1 <= v <= 65535):
            raise ValueError('port must be between 1 and 65535')
        if values.get('type') == 'tcp' and v is None:
            raise ValueError('port is required for tcp health check')
        return v

    @validator('host')
    def validate_host_for_tcp(cls, v, values):
        if values.get('type') == 'tcp' and v is None:
            raise ValueError('host is required for tcp health check')
        return v

    @validator('command')
    def validate_command_for_command_type(cls, v, values):
        if values.get('type') == 'command' and v is None:
            raise ValueError('command is required for command health check')
        return v


class LogConfigSchema(BaseModel):
    type: str # cloudwatch
    log_group: Optional[str] = None
    region: Optional[str] = None


class AppConfigSchema(BaseModel):
    name: str
    type: str # lambda, kubernetes, docker, custom
    description: Optional[str] = None
    added_at: str
    lambda_config: Optional[Dict[str, Any]] = Field(None, alias="lambda") # Use alias for "lambda" keyword
    kubernetes: Optional[Dict[str, Any]] = None
    docker: Optional[Dict[str, Any]] = None
    logs: Optional[LogConfigSchema] = None
    health: Optional[HealthCheckSchema] = None
    aws_role: Optional[str] = None
    teams: List[str] = ["default"]

    @validator('name')
    def validate_name(cls, v):
        if not re.match(r"^[a-zA-Z0-9_\-]+$", v):
            raise ValueError("name must be alphanumeric, dash, or underscore")
        return v


class WebsiteConfigSchema(BaseModel):
    name: str
    url: HttpUrl
    expected_status: int = 200
    timeout: int = 10
    method: str = "GET" # GET, POST, HEAD
    headers: Dict[str, str] = Field(default_factory=dict)
    enabled: bool = True
    added_at: str
    teams: List[str] = ["default"]

    @validator('url', pre=True)
    def convert_url_to_str(cls, v):
        if isinstance(v, HttpUrl):
            return str(v)
        return v


class ServerConfigSchema(BaseModel):
    name: str
    host: str
    user: str = "deploy"
    port: int = 22
    key: str = "~/.ssh/id_rsa"
    tags: List[str] = Field(default_factory=list)
    added_at: str
    teams: List[str] = ["default"]


class AwsRoleSchema(BaseModel):
    role_arn: str
    region: str
    external_id: Optional[str] = None
    description: Optional[str] = None
    added_at: str


class AwsConfigSchema(BaseModel):
    organization: str
    default_region: str
    roles: Dict[str, AwsRoleSchema] = Field(default_factory=dict)
    created_at: str
    created_by: str


class TeamAccessSchema(BaseModel):
    name: str
    description: Optional[str] = None
    apps: List[str] = ["*"]
    servers: List[str] = ["*"]
    websites: List[str] = ["*"]
    created_at: str


class TeamsConfigSchema(BaseModel):
    organization: str
    teams: Dict[str, TeamAccessSchema] = Field(default_factory=dict)


class FullConfigSchema(BaseModel):
    exported_at: str
    aws: Optional[AwsConfigSchema] = None
    apps: Dict[str, AppConfigSchema] = Field(default_factory=dict)
    servers: Dict[str, ServerConfigSchema] = Field(default_factory=dict)
    websites: Dict[str, WebsiteConfigSchema] = Field(default_factory=dict)
    teams: Optional[TeamsConfigSchema] = None
