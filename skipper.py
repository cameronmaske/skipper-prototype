import aaargh
from boto import ec2
from boto.exception import EC2ResponseError

from fabric.context_managers import settings, local_tunnel
from fabric.api import run, sudo
from fabric.contrib.files import upload_template, contains, append
import time
import docker


from config import Config
from utils import find

app = aaargh.App(description="A prototype of skipper.")


def get_or_create_security_group(c):
    groups = c.get_all_security_groups()
    group = find(groups, {'name': 'skipper'})
    if not group:
        print("Creating new security group.")
        group = c.create_security_group("skipper", "Skipper security group")
    else:
        print("Found existing security group.")
    return group


def authorize_group(group, ip_protocol, from_port, to_port, cidr_ip):
    """
    Agruments:
        group: Security Group
        ip_protocol: 'tcp'
        from_port: 22
        to_port: 22
        cidr_ip: '192.168.1.130/32'
    """
    for i in range(5):
        try:
            group.authorize(ip_protocol, from_port, to_port, cidr_ip)
            break
        except EC2ResponseError as e:
            if e.code == 'InvalidPermission.Duplicate':
                break
            time.sleep(2)


def all_hosts(c):
    reserved = c.get_all_instances()
    instances = []
    for r in reserved:
        for i in r.instances:
            if i.state != "terminated" and i.tags.get('type') == "skipper":
                instances.append(i)
    return instances


def create_host(c):
    reservation = c.run_instances(**{
        'image_id': 'ami-a73264ce',  # Ubuntu 12.04.1
        'instance_type': 't1.micro',
        #'security_groups': ['skipper'],
        'key_name': 'skipper'
    })
    instance = reservation.instances[0]

    print('Waiting for instance to boot up.')

    while instance.state != 'running':
        time.sleep(2)
        instance.update()
        print "Instance state: " + instance.state

    if instance.state == 'running':
        print('Instance is now running.')
        instance.add_tag('type', 'skipper')

    print("Waiting 15 seconds for good measure.")
    time.sleep(15)

    return instance


def get_or_create_test_host(c):
    instances = all_hosts(c)
    test_host = find(instances, {'tags': {'name': 'test_host', 'type': 'skipper'}})
    if not test_host:
        test_host = create_host(c)
        test_host.add_tag('name', 'test_host')
    return test_host


def get_key(c):
    keys = c.get_all_key_pairs()
    match = find(keys, {'name': 'skipper'})
    return match


def create_key(c):
    key = c.create_key_pair('skipper')
    return key


def connect(acesss_key, secret_key):
    return ec2.connection.EC2Connection(acesss_key, secret_key)


def get_config():
    config = Config()
    if not config['ACCESS_KEY']:
        access_key = raw_input("Enter your access key: ")
        config['ACCESS_KEY'] = access_key
    if not config['SECRET_KEY']:
        secret_key = raw_input("Enter your secret key: ")
        config['SECRET_KEY'] = secret_key
    return config


def load_balance(ports):
    nginx_file = "/etc/nginx/nginx.conf"
    context = {
        'ports': ports
    }
    upload_template('nginx.template', destination=nginx_file, context=context, use_jinja=True, use_sudo=True)
    sudo('cat /etc/nginx/nginx.conf')
    sudo('/etc/init.d/nginx configtest && sudo /etc/init.d/nginx reload')


def already_exists(version, containers):
    for item in containers:
        joined_name = '-'.join(item['Names']).replace('/', '', 1)
        name, container_version = joined_name.split('_', 1)
        if name == 'skipper' and container_version == version:
            return item
    return False


def existing_containers(containers):
    existing = []
    for item in containers:
        joined_name = '-'.join(item['Names']).replace('/', '', 1)
        name, container_version = joined_name.split('_', 1)
        if name == 'skipper':
            existing.append(item)
    return existing


@app.cmd
def deploy():
    version = raw_input("Enter the version to deploy [v1 or v2]: ")
    if version not in ['v1', 'v2']:
        print("Only currenly two versions (v1, v2)")
        return

    config = get_config()
    c = connect(config['ACCESS_KEY'], config['SECRET_KEY'])

    if not config['PRIVATE_KEY']:
        print('Go private key stored. Will attempt to generate.')
        existing_key = get_key(c)
        if existing_key:
            print('A private key already exists, gonna remove it.')
            existing_key.delete()
        print('Creating and storing private key.')
        key = create_key(c)
        config['PRIVATE_KEY'] = key.material

    print('Checking if a security group exists.')
    group = get_or_create_security_group(c)
    authorize_group(group, 'tcp', 22, 22, '0.0.0.0/0')
    authorize_group(group, 'tcp', 80, 80, '0.0.0.0/0')

    print('Checking if a test host exists.')
    host = get_or_create_test_host(c)
    host.modify_attribute('groupSet', [group.id])

    params = {
        'user': 'ubuntu',
        'host_string': host.public_dns_name
    }
    with settings(key=config['PRIVATE_KEY'], **params):

        installed = run('which docker', warn_only=True)
        if not installed:
            print("Attempting to install Docker.")
            sudo('sh -c "wget -qO- https://get.docker.io/gpg | apt-key add -"')
            sudo('sh -c "echo deb http://get.docker.io/ubuntu docker main > /etc/apt/sources.list.d/docker.list"')
            sudo('apt-get update')
            sudo('apt-get -y install linux-image-extra-virtual')
            sudo('apt-get -y install lxc-docker-0.9.0')
            sudo('apt-get update')
            time.sleep(10)

        run('docker --version')

        nginx = run('which nginx', warn_only=True)
        if not nginx:
            sudo('apt-get install -y nginx')
            sudo('service nginx start')

        if not contains('/etc/default/docker', 'DOCKER_OPTS="-H tcp://0.0.0.0:5555 -H unix://var/run/docker.sock"'):
            append('/etc/default/docker', 'DOCKER_OPTS="-H tcp://0.0.0.0:5555 -H unix://var/run/docker.sock"', use_sudo=True)
            sudo('service docker restart')

        with local_tunnel(5555, bind_port=59432):
            client = docker.Client(
                base_url="http://localhost:59432")

            print client.images()
            print client.containers(all=True)

            for item in existing_containers(client.containers()):
                client.stop(item['Id'])

            if already_exists(version, client.containers()):
                print('Already running {}'.format(version))
            else:
                old = existing_containers(client.containers())
                # Need to pull the image before creating the container.
                exists = already_exists(version, client.containers(all=True))
                if exists:
                    print exists
                    c_id = exists['Id']
                else:
                    image_name = 'cameronmaske/node-server:{}'.format(version)
                    client.pull(image_name)
                    c_id = client.create_container(image_name, ports=[1337], name="skipper_{}".format(version))
                client.start(c_id, port_bindings={1337: None})
                container = client.inspect_container(c_id)
                ports = get_ports(container)
                load_balance([ports['host']['port']])
                for item in old:
                    client.stop(item['Id'])


def clean_port(dirty):
    clean = dirty.replace('/tcp', '')
    return int(clean)


def get_ports(container):
    clean_ports = {}
    ports = container['NetworkSettings']['Ports']
    for guest, host in ports.items():
        clean_ports['guest'] = {
            'port': clean_port(guest)
        }

        if len(host) == 1:
            host_port = clean_port(host[0]['HostPort'])
            clean_ports['host'] = {
                'port': host_port,
                'ip': host[0]['HostIp']
            }

    return clean_ports


if __name__ == '__main__':
    app.run()
