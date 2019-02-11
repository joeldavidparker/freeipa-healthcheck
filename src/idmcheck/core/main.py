import pkg_resources
from idmcheck.core.plugin import Result, Results, JSON
from idmcheck.core import constants
from idmcheck.meta.services import ServiceCheck
from pprint import pprint

def find_registries():
    return {
        ep.name: ep.resolve()
        for ep in pkg_resources.iter_entry_points('idmcheck.registry')
    }


def find_plugins(name, registry):
    for ep in pkg_resources.iter_entry_points(name):
        # load module
        ep.load()
    return registry.get_plugins()


def run_plugin(plugin, available=()):
    try:
        result = plugin.check()
        if type(result) not in (Result, Results):
            # Treat no result as success
            result = Result(plugin, constants.SUCCESS)
    except Exception as e:
        print('Exception raised: %s', e)
        result = Result(plugin, constants.CRITICAL, exception=str(e))

    return result


def run_service_plugins(plugins):
    results = Results()
    available = []

    for plugin in plugins:
        if not isinstance(plugin, ServiceCheck):
            continue

        result = run_plugin(plugin)

        if result.severity == constants.SUCCESS:
            available.append(plugin.service_name)

        if isinstance(result, Result):
            results.add(result)
        elif isinstance(result, Results):
            results.extend(result)

    return results, set(available)


def run_plugins(plugins, available):
    results = Results()

    for plugin in plugins:
        if isinstance(plugin, ServiceCheck):
            continue

        # TODO: make this not the default
        if not set(plugin.requires).issubset(available):
            result = Result(plugin, constants.ERROR,
                            msg='%s service(s) not running' %
                            (', '.join(set(plugin.requires) - available)))
        else:
            result = run_plugin(plugin, available)

        if isinstance(result, Result):
            results.add(result)
        elif isinstance(result, Results):
            results.extend(result)

    return results

def main():
    framework = object()
    plugins = []

    for name, registry in find_registries().items():
        registry.initialize(framework)
        print(name, registry)
        for plugin in find_plugins(name, registry):
            plugins.append(plugin)

    results, available = run_service_plugins(plugins)
    results.extend(run_plugins(plugins, available))

    output = JSON()
    output.render(results)
