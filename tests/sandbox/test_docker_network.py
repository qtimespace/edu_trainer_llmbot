"""Сеть песочниц: межсетевой экран завязан на мост trbr-sandbox и подсеть 172.31.250.0/24 — чужая сеть с тем же
именем не должна молча использоваться (экран бы не сработал)."""
from types import SimpleNamespace

import pytest

from trainer.sandbox.docker_backend import DockerBackend, SandboxNetworkError
from trainer.settings import Settings


class FakeNetworks:
    def __init__(self, existing):
        self.existing, self.created = existing, []

    def list(self, names):
        return self.existing

    def create(self, name, **kw):
        self.created.append((name, kw))


def _backend(existing):
    backend = DockerBackend.__new__(DockerBackend)
    backend._settings = Settings(_env_file=None)
    backend._network_ready = False
    backend._client = SimpleNamespace(networks=FakeNetworks(existing))
    return backend


def _net(bridge, subnet):
    return SimpleNamespace(attrs={"Options": {"com.docker.network.bridge.name": bridge} if bridge else {},
                                  "IPAM": {"Config": [{"Subnet": subnet}]}})


def test_creates_pinned_network():
    b = _backend([])
    b._ensure_network()
    name, kw = b._client.networks.created[0]
    assert kw["options"]["com.docker.network.bridge.name"] == "trbr-sandbox"


def test_accepts_pinned_existing_network():
    b = _backend([_net("trbr-sandbox", "172.31.250.0/24")])
    b._ensure_network()
    assert b._client.networks.created == []


@pytest.mark.parametrize("bridge,subnet", [(None, "172.18.0.0/16"), ("br-abc", "172.31.250.0/24"),
                                           ("trbr-sandbox", "10.0.0.0/24")])
def test_refuses_unpinned_existing_network(bridge, subnet):
    with pytest.raises(SandboxNetworkError):
        _backend([_net(bridge, subnet)])._ensure_network()
