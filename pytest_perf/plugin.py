import pytest
import configparser

from typing import List

from pytest_perf import runner


def pytest_configure(config):
    Item.runner = runner.BenchmarkRunner()


def pytest_collect_file(parent, path):
    if path.basename == 'exercises.ini':
        return File.from_parent(parent, fspath=path)


def pytest_terminal_summary(terminalreporter, config):
    terminalreporter.write('\n')
    terminalreporter.write('Perf results:\n')
    for item in Item._instances:
        terminalreporter.write(str(item) + '\n')


class File(pytest.File):
    def collect(self):
        config = configparser.ConfigParser()
        config.read(self.fspath)
        return (
            Item.from_parent(self, name=section, spec=config[section])
            for section in config.sections()
        )


class Item(pytest.Item):
    _instances: 'List[Item]' = []

    def __init__(self, name, parent, spec):
        super().__init__(name, parent)
        self.command = runner.Command(**spec)
        Item._instances.append(self)

    def runtest(self):
        self.results = self.runner.run(self.command)

    def reportinfo(self):
        return self.fspath, 0, self.name

    def __str__(self):
        return f'{self.name}: {self.results}'
