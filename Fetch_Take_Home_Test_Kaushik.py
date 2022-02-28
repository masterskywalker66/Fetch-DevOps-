
import yaml
import boto3, time
from collections import defaultdict
import traceback

KEYNAME = 'fetch-keypair'
IMAGES = {}
IMAGES ['amzn2-hvm-x86_64'] = 'ami-033b95fb8079dc481'
# IP range of machines requiring SSH access
MYIP = '0.0.0.0/0'

def send_cmd(region,cmd,id):
    """ Use describe instance information to get instance id base on region """
    ssm_filter = [{'Key': 'tag:SSM', 'Values': ['ssm-cmd']}]
    ssm = boto3.client('ssm', region_name=region)
    #instance_info = ssm.describe_instance_information(Filters=ssm_filter).get('InstanceInformationList', {})[0]
    #instance_id = instance_info.get('InstanceId', '')
    response = ssm.send_command(InstanceIds=[id],
                                DocumentName='AWS-RunShellScript',
                                Parameters={"commands": [cmd]}
                                )
    command_id = response.get('Command', {}).get("CommandId", None)
    while True:
        """ Wait for SSM response """
        response = ssm.list_command_invocations(CommandId=command_id, Details=True)
        """ If the command hasn't started to run yet, keep waiting """
        if len(response['CommandInvocations']) == 0:
            time.sleep(1)
            continue
        invocation = response['CommandInvocations'][0]
        if invocation['Status'] not in ('Pending', 'InProgress', 'Cancelling'):
            break
        time.sleep(1)
    command_plugin = invocation['CommandPlugins'][-1]
    output = command_plugin['Output']
    print(f"Complete running, output: {output}")

print("Reading YAML file")
with open('testconfig.yaml', 'r') as yaml_file:
    try:
        print("Safeloading YAML")
        jsonFormat = yaml.safe_load(yaml_file)
    except yaml.YAMLError as e:
        print(e)

print("Defining Volumes and users")
try:
    ec2 = boto3.resource('ec2')
   
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
        usercmds += 'adduser %s\n'        % (i['login'])
        usercmds += 'mkdir /home/%s/.ssh\n' % (i['login'])
        usercmds += 'touch /home/%s/.ssh/authorized_keys\n' % (i['login'])
        usercmds += 'echo %s > /home/%s/.ssh/authorized_keys\n' % (i['ssh_key'], i['login'])

        usercmds += 'mkdir /tempUser1\n'
        usercmds += 'echo %s > /tempUser1/readMe.txt\n' % (content1)
        usercmds += 'mkdir /data/tempUser2\n'
        usercmds += 'echo %s > /data/tempUser2/readMe.txt\n' % (content2)

        region = 'us-east-1'
        usercmds += """#cloud-config
        runcmd:
        - /home/ec2-user/sudo npm run prod
        - cd /tmp
        - curl https://amazon-ssm-%s.s3.amazonaws.com/latest/linux_amd64/amazon-ssm-agent.rpm -o amazon-ssm-agent.rpm
        - yum install -y amazon-ssm-agent.rpm
        - sudo systemctl enable amazon-ssm-agent""" % region   




    #print(usercmds," User Data 2")

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

    send_cmd('us-east-1','cat /tempUser1/readMe.txt',instance[0]['Instances'][0]['InstanceId'])
    send_cmd('us-east-1','cat /data/tempUser2/readMe.txt',instance[0]['Instances'][0]['InstanceId'])


    #try:
    #    ec2client = boto3.client('ssm')
    #    print(instance[0]['Instances'][0]['InstanceId']," Ok this is it")
    #    response = ec2client.send_command(
    #        InstanceIds=[instance[0]['Instances'][0]['InstanceId']],
    #        DocumentName="AWS-RunShellScript",
    #        Parameters={'commands': ['cat /tempUser1/readMe.txt']}, )

    #    command_id = response['Command']['CommandId']
    #    output = ec2client.get_command_invocation(
    #        CommandId=command_id,
    #        InstanceId=[instance[0]['Instances'][0]['InstanceId']],
    #        )
    #    print(output)

    #    response = ec2client.send_command(
    #        InstanceIds=[[instance[0]['Instances'][0]['InstanceId']]],
    #        DocumentName="AWS-RunShellScript",
    #        Parameters={'commands': ['cat /data/tempUser2/readMe.txt']}, )

    #    command_id = response['Command']['CommandId']
    #    output = ec2client.get_command_invocation(
    #        CommandId=command_id,
    #        InstanceId=[instance[0]['Instances'][0]['InstanceId']],
    #        )
    #    print(output)



    #    #client = boto3.client('ec2')

    #    #readCmd1 = 'cat /tempUser1/readMe.txt'
    #    #readCmd2 = 'cat /data/tempUser2/readMe.txt'
    #    #stdin,stdout,stderr = client.exec_command(readCmd1)
    #    #print("This is the content read from Volume 1 ",stdout.read())
    #    #stdin,stdout,stderr = client.exec_command(readCmd2)
    #    #print("This is the content read from Volume 2 ",stdout.read())

    #except Exception as e:
    #    traceback.print_exc()
    #    print(e)

except Exception as e:
    print(type(e).__name__)
    print('Could not create instance.')
    traceback.print_exc()






