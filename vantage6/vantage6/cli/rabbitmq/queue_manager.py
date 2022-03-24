import docker
import json
import os
import shutil
import base64
import hashlib

from pathlib import Path
from typing import Dict

from vantage6.common.globals import APPNAME
from vantage6.common.docker_addons import remove_container_if_exists
from vantage6.cli.context import ServerContext
from vantage6.cli.rabbitmq.definitions import RABBITMQ_DEFINITIONS

# TODO which image to use for final? Consider also frequency of renewal
RABBIT_IMAGE = 'rabbitmq:3-management'
RABBIT_CONFIG = 'rabbitmq.config'
RABBIT_DIR = 'rabbitmq'
QUEUE_PORT = 5672


def get_rabbitmq_uri(rabbit_config: Dict) -> str:
    """
    Get the URI to reach the RabbitMQ queue

    Parameters
    ----------
    rabbit_config: Dict
        A dictionary with username and password for RabbitMQ queue

    Returns
    -------
    str
        The URI at which the RabbitMQ queue can be reached
    """
    VHOST = '/test'
    return (
        f"amqp://{rabbit_config['user']}:{rabbit_config['password']}@"
        f"host.docker.internal:{QUEUE_PORT}/{VHOST}"
    )


class RabbitMQManager:
    """
    Manages the RabbitMQ docker container
    """
    def __init__(self, ctx: ServerContext) -> None:
        """
        Parameters
        ----------
        ctx: ServerContext
            Configuration object
        queue_uri: str
            URI where the RabbitMQ instance should be running
        """
        self.ctx = ctx
        rabbit_settings = self.ctx.config.get('rabbitmq')
        self.rabbit_user = rabbit_settings['user']
        self.rabbit_pass = rabbit_settings['password']
        self.queue_uri = get_rabbitmq_uri(rabbit_settings)
        self.docker = docker.from_env()

        # TODO is this always unique?
        self.rabbit_container_name = f'{APPNAME}-{ctx.name}-rabbitmq'

    def start(self):
        """
        Start a docker container which runs a RabbitMQ queue
        """
        # get volumes which contain
        volumes = self._get_volumes()

        # expose port 5672 inside the container as port 5672 on the host, and
        # same for 15672 in container to 8080 on host
        # TODO check if these ports are available on the host (?)
        ports = {
            f'{QUEUE_PORT}/tcp': QUEUE_PORT,
            # TODO this is for the management tool, do we keep this?
            '15672/tcp': 8080
        }

        # if a RabbitMQ container is already running, kill and remove it
        remove_container_if_exists(
            docker_client=self.docker, name=self.rabbit_container_name
        )

        # run rabbitMQ container
        self.rabbit_container = self.docker.containers.run(
            name=self.rabbit_container_name,
            image=RABBIT_IMAGE,
            volumes=volumes,
            ports=ports,
            detach=True,
            restart_policy={"Name": "always"},
            hostname=f'{APPNAME}-{self.ctx.name}-rabbit',
            labels={
                f"{APPNAME}-type": "rabbitmq",
            }
        )

    def _get_volumes(self) -> Dict:
        """
        Prepare the volumes for the RabbitMQ container. The RabbitMQ should
        set up the right vhost and users to allow the server to communicate
        with RabbitMQ as configured.
        """
        # default RabbitMQ configuration: replace the user/password with the
        # credentials from the configuraiton
        rabbit_definitions = self._get_rabbitmq_definitions()

        # write the RabbitMQ definition to file(s)
        definitions_filepath = Path(self.ctx.data_dir / 'definitions.json')
        with open(definitions_filepath, 'w') as f:
            json.dump(rabbit_definitions, f, indent=2)

        # write RabbitMQ config to file
        rabbit_conf = \
            Path(os.path.dirname(os.path.realpath(__file__))) / RABBIT_CONFIG
        shutil.copyfile(rabbit_conf, self.ctx.data_dir / RABBIT_CONFIG)

        # check if a directory for persistent RabbitMQ storage exists,
        # otherwise create it
        rabbit_data_dir = self.ctx.data_dir / RABBIT_DIR
        if not os.path.exists(rabbit_data_dir):
            os.makedirs(rabbit_data_dir)

        return {
            definitions_filepath: {
                'bind': '/etc/rabbitmq/definitions.json', 'mode': 'ro'
            },
            self.ctx.data_dir / RABBIT_CONFIG: {
                'bind': '/etc/rabbitmq/rabbitmq.config', 'mode': 'ro'
            },
            rabbit_data_dir: {
                'bind': '/var/lib/rabbitmq', 'mode': 'rw'
            }
        }

    def _get_rabbitmq_definitions(self) -> Dict:
        """
        Get startup definitions (users/vhosts etc) for RabbitMQ container

        Returns
        -------
        Dict:
            dictionary with all users/vhosts etc that must be generated on
            startup of RabbitMQ
        """
        rabbit_definitions = RABBITMQ_DEFINITIONS
        rabbit_definitions['users'][0]['name'] = self.rabbit_user
        rabbit_definitions['permissions'][0]['user'] = self.rabbit_user
        rabbit_definitions['users'][0]['password_hash'] = \
            self._get_hashed_pw(self.rabbit_pass)
        return rabbit_definitions

    def _get_hashed_pw(self, pw):
        """ Hash a user-defined password for RabbitMQ """

        # Generate a random 32 bit salt:
        salt = os.urandom(4)

        # Concatenate that with the UTF-8 representation of the password
        tmp0 = salt + pw.encode('utf-8')

        # Take the SHA256 hash and get the bytes back
        tmp1 = hashlib.sha256(tmp0).digest()

        # Concatenate the salt again:
        salted_hash = salt + tmp1

        # convert to base64 encoding:
        pass_hash = base64.b64encode(salted_hash)
        return pass_hash.decode('utf-8')
