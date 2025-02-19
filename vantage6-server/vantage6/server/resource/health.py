# -*- coding: utf-8 -*-
import logging

from http import HTTPStatus
from sqlalchemy.exc import InvalidRequestError
from flask.globals import g

from vantage6.server.resource import ServicesResources
from vantage6.common import logger_name


module_name = logger_name(__name__)
log = logging.getLogger(module_name)


def setup(api, api_base, services):

    path = "/".join([api_base, module_name])
    log.info(f'Setting up "{path}" and subdirectories')

    api.add_resource(
        Health,
        path,
        endpoint='health',
        methods=('GET',),
        resource_class_kwargs=services
    )

    api.add_resource(
        Fix,
        path + "/fix",
        methods=('GET',),
        resource_class_kwargs=services
    )


# ------------------------------------------------------------------------------
# Resources / API's
# ------------------------------------------------------------------------------
class Health(ServicesResources):

    def get(self):
        """Displays the health of services
        ---
        description: >-
          Checks if server can communicate with the database. If not, it throws
          an exception.

        responses:
          200:
            description: Ok

        security:
        - bearerAuth: []

        tags: ["Database"]
        """

        # test DB
        db_ok = False
        try:
            g.session.execute('SELECT 1')
            db_ok = True
        except Exception as e:
            log.error("DB not responding")
            log.debug(e)

        return {'database': db_ok}, HTTPStatus.OK


class Fix(ServicesResources):

    def get(self):
        """Experimental switch to fix db errors"""

        try:
            g.session.execute('SELECT 1')

        except (InvalidRequestError, Exception) as e:
            log.error("DB nudge... Does this work?")
            log.debug(e)
            # session.invalidate()
            # session.rollback()

        # finally:
        #     session.close()
