
from distutils.command.config import config
import yaml
import boto3, time
import paramiko
from collections import defaultdict
import traceback
import os.path

KEYNAME = 'fetch-keypair' 
IMAGES = {}
IMAGES ['amzn2-hvm-x86_64'] = 'ami-033b95fb8079dc481'
# IP range of machines requiring SSH access
MYIP = '0.0.0.0/0'

def send_cmd(cmd,id):
    
    ec2 = boto3.Session(profile_name='default', region_name='us-east-1').client('ec2')

    ROOT_DIR = os.path.dirname(os.path.abspath("fetch_keypair.pem"))
    ROOT_DIR = ROOT_DIR + "/fetch-keypair.pem"
    k = paramiko.RSAKey.from_private_key_file(ROOT_DIR)
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(id,k)
    c.connect(hostname=id, username='ec2-user', pkey=k)   

    for command in cmd:
        print("Executing: {}".format(command))
        stdin , stdout, stderr = c.exec_command(command)
        print(stdout.read().decode('ascii'))
        #print(stderr.read())

    c.close()

print("Reading YAML file")
with open('config.yaml', 'r') as yaml_file:
    try:
        print("Safeloading YAML")
        jsonFormat = yaml.safe_load(yaml_file)
    except yaml.YAMLError as e:
        print(e)

print("Defining Volumes and users")
try:
    ec2 = boto3.resource('ec2')
    ROOT_DIR = os.path.dirname(os.path.abspath("config.yaml"))
    ROOT_DIR = ROOT_DIR + "/fetch-keypair.pem"
    if not os.path.exists(ROOT_DIR):
    # create keypairs
        with open(KEYNAME+'.pem', 'w') as keyPairFile:
            try:
                key_pair = ec2.create_key_pair(KeyName=KEYNAME)
                print("KeyPair ",key_pair.key_material)
                keyPairFile.write(str(key_pair.key_material))
            except Exception as e:
                print('Key pair already exists')
                #print(e)

    conf = jsonFormat['server']

    ami = conf['ami_type'] + '-' + conf['virtualization_type'] + '-' + conf['architecture'];

    vol = []
    for volume in conf['volumes']:
        vol.append(volume)

    usr = []
    for user in conf['users']:
        usr.append(user)

    usercmds = '#!/bin/bash\n'
    content1 = "Please send me goodies once i join the company!"
    content2 = 'I really like hoodies'

    for i in vol:
        usercmds += 'mkfs.%s %s\n'        % (i['type'], i['device'])
        usercmds += 'mkdir %s\n'          % (i['mount'])
        usercmds += 'mount -o rw %s %s\n' % (i['device'], i['mount'])

    for i in usr:
        usercmds += 'useradd -r %s\n'        % (i['login'])
        usercmds += 'mkdir /home/%s/.ssh\n' % (i['login'])
        usercmds += 'touch /home/%s/.ssh/authorized_keys\n' % (i['login'])
        usercmds += 'echo %s > /home/%s/.ssh/authorized_keys\n' % (i['ssh_key'], i['login'])

        #usercmds += 'chmod 777 -R /\n'
        # usercmds += 'echo %s > /tempUser1/readMe.txt\n' % (content1)
        # usercmds += 'mkdir /data/tempUser2\n'
        # usercmds += 'echo %s > /data/tempUser2/readMe.txt\n' % (content2)

        region = 'us-east-1'
        usercmds += """#cloud-config
        runcmd:
        - /home/ec2-user/sudo npm run prod
        - cd /tmp
        - curl https://amazon-ssm-%s.s3.amazonaws.com/latest/linux_amd64/amazon-ssm-agent.rpm -o amazon-ssm-agent.rpm
        - yum install -y amazon-ssm-agent.rpm
        - sudo systemctl enable amazon-ssm-agent""" % region   

    BDM = []
    for i in vol:
        data = {
                'DeviceName': i['device'],
                'Ebs': {
                    'VolumeSize': i['size_gb']
                }
            }
        BDM.append(data)
    print(BDM)
    # create a new EC2 instance
    instances = ec2.create_instances(
        KeyName=KEYNAME,
        ImageId=IMAGES[ami],
        InstanceType=conf['instance_type'],
        MinCount=conf['min_count'],
        MaxCount=conf['max_count'],
        UserData=usercmds,
        BlockDeviceMappings=BDM
    )

    # wait for instance initialization
    print('Instance created, initialization pending ... ')
    instanceIds=[instances[0].id]
    waiter = ec2.meta.client.get_waiter('instance_running')
    waiter.wait(InstanceIds=instanceIds)
    print(' ... running!')

    print('Authorizing security group ingress for SSH ...')
    try:
        # allow inbound ssh rules
        client = boto3.client('ec2')
        describe = client.describe_instances()
        sgId = describe['Reservations'][-1]['Instances'][0]['SecurityGroups'][0]['GroupId']
        resp = client.authorize_security_group_ingress(
            GroupId=sgId,
            IpPermissions=[
                {'IpProtocol': 'tcp',
                 'FromPort': 80,
                 'ToPort': 80,
                 'IpRanges': [{'CidrIp': MYIP}]},
                {'IpProtocol': 'tcp',
                 'FromPort': 22,
                 'ToPort': 22,
                 'IpRanges': [{'CidrIp': MYIP}]}
        ])

        
        # (same as via cli)
        # $> aws ec2 describe-instance-attribute --instance-id instance_id --attribute groupSet
        # $> aws ec2 authorize-security-group-ingress --group-id security_group_id --protocol tcp --port 22 --cidr MYIP
    except Exception as e:
        traceback.print_exc()
        print(' .. ')
    

    print('Instance public ip address:')
    instance = list(filter(lambda x: x['Instances'][0]['InstanceId']==instances[0].id, describe['Reservations']))
    print(instance[0]['Instances'][0]['PublicIpAddress'])
    print(instance)

    cmmd1 = 'echo %s > /tempUser1/readMe.txt' % (content1)
    cmmd2 = 'echo %s > /data/readMe.txt' % (content2)

    commands = [
        'cd /','sudo mkdir /data','sudo chmod 777 -R /data','sudo mkdir /tempUser1','sudo chmod 777 -R /tempUser1',
        cmmd1,cmmd2,
        'sudo cat /tempUser1/readMe.txt',
        'sudo cat /data/readMe.txt',
    ]

    send_cmd(commands,instance[0]['Instances'][0]['PublicIpAddress'])


except Exception as e:
    print(type(e).__name__)
    print('Could not create instance.')
    traceback.print_exc()
