from utils import find, get_subset
from config import BaseConfig
from skipper import get_ports, clean_port


def test_get_subset():
    foo = {'a': 1, 'b': 2, 'c': 3}
    subset = get_subset(foo, ['a'])
    assert subset == {'a': 1}
    subset = get_subset(foo, ['a', 'b'])
    assert subset == {'a': 1, 'b': 2}


def test_find():
    looking_for = {'a': 1, 'match': True}
    foo = [looking_for, {'b': 1}, {'a': 2}]
    match = find(foo, {'a': 1})
    assert match == looking_for
    match = find(foo, {'c': 1})
    assert not match


def test_config():
    config = BaseConfig()
    config['access_key'] = 'foo'
    assert config['access_key'] == 'foo'


def test_clean_port():
    assert clean_port('1337/tcp') == 1337
    assert clean_port('49153') == 49153


def test_get_ports():
    container = {
        'NetworkSettings': {
            'Ports': {
                '1337/tcp': [{'HostPort': '49153', 'HostIp': '0.0.0.0'}]
            }
        }
    }

    ports = get_ports(container)

    expected = {
        'guest': {
            'port': 1337
        },
        'host': {
            'port': 49153,
            'ip': '0.0.0.0'
        }
    }

    assert ports == expected
