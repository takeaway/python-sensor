from __future__ import absolute_import

import opentracing
import wrapt

from ...log import logger
from ...singletons import agent, async_tracer
from ...util import strip_secrets


def handle_aiohttp_exception(scope, exception, http_status_code=500):
    logger.debug("aiohttp stan_middleware", exc_info=True)
    if scope is not None:

        if hasattr(getattr(exception, 'headers', None), '__setitem__'):
            async_tracer.inject(scope.span.context, opentracing.Format.HTTP_HEADERS, exception.headers)
            exception.headers['Server-Timing'] = "intid;desc=%s" % scope.span.context.trace_id

        scope.span.set_tag("http.status_code", http_status_code)
        if 500 <= http_status_code <= 511:
            scope.span.log_exception(exception)


try:
    import aiohttp
    import asyncio

    from aiohttp.web import middleware

    @middleware
    async def stan_middleware(request, handler):
        try:
            ctx = async_tracer.extract(opentracing.Format.HTTP_HEADERS, request.headers)
            request['scope'] = async_tracer.start_active_span('aiohttp-server', child_of=ctx)
            scope = request['scope']

            # Query param scrubbing
            url = str(request.url)
            parts = url.split('?')
            if len(parts) > 1:
                cleaned_qp = strip_secrets(parts[1], agent.secrets_matcher, agent.secrets_list)
                scope.span.set_tag("http.params", cleaned_qp)

            scope.span.set_tag("http.url", parts[0])
            scope.span.set_tag("http.method", request.method)

            # Custom header tracking support
            if hasattr(agent, 'extra_headers') and agent.extra_headers is not None:
                for custom_header in agent.extra_headers:
                    if custom_header in request.headers:
                        scope.span.set_tag("http.%s" % custom_header, request.headers[custom_header])

            response = await handler(request)

            if response is not None:
                # Mark 500 responses as errored
                if 500 <= response.status <= 511:
                    scope.span.mark_as_errored()

                scope.span.set_tag("http.status_code", response.status)
                async_tracer.inject(scope.span.context, opentracing.Format.HTTP_HEADERS, response.headers)
                response.headers['Server-Timing'] = "intid;desc=%s" % scope.span.context.trace_id

            return response

        except aiohttp.web_exceptions.HTTPError as e:
            handle_aiohttp_exception(scope, e, e.status_code)
            raise

        except Exception as e:
            handle_aiohttp_exception(scope, e, 500)
            raise
        finally:
            if scope is not None:
                scope.close()


    @wrapt.patch_function_wrapper('aiohttp.web','Application.__init__')
    def init_with_instana(wrapped, instance, argv, kwargs):
        if "middlewares" in kwargs:
            kwargs["middlewares"].insert(0, stan_middleware)
        else:
            kwargs["middlewares"] = [stan_middleware]

        return wrapped(*argv, **kwargs)

    logger.debug("Instrumenting aiohttp server")
except ImportError:
    pass
