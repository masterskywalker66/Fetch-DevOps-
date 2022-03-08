Fetch DevOps TakeHome Test, Documentation
-- Kaushik Govindharajan

The program reads a YAML configuration file and creates an AWS Linux EC2 instance based on the specifications provided. The Program also has Linux user commands that instruct the Instance to spin up two volumes and two users and gives both users SSH access into the server and they are able to read and write to each of the two volumes. The program utilizes boto3 client to relay commands to AWS and communitcate with AWS resources. 

The user will need to create an AWS 'user' and enable programmatic access (to operate the command line interface with). The Access ID kay and Secret Access key are necessary when trying to loging to the aws server through your local host. . We would also need to attach the AWSEC2FullAccess and AWSSSM oilicies to our user as AWS follows the principle of least privilages and any access/permissions have to be explicitly provided. Using aws configure, set up your user and enter in your Access ID and Secret Access key so that you are now able to access the EC2 instance. 

On running the code, it will display the status of the program as it goes through the steps. It first parses the config file and takes out the values - the instance type, amitype, architecture, number of instances, number of volumes, size of the volumes, where they are mounted, etc. We use a loop to go through the file, even though it is mentioned that there are only 2 volumes to be created - this makes the code scalable if there are more volumes to be added in the future. The SSH keys for user1 and user2 are generated using a KeyGen tool and are entered into the YAML file, so that it is easily available to be sent to AWS to authenticate the users when they try to access it. 

Once the entire program executes, it will have created the AWS Linux 2 instance and will run the user commands on it to create volumes, users and then write and read text. It sould display the output of the text file stored in the two volumes. 

Note: Please run it once at a time. If an instance is already running, it is preferable to terminate it before the program is run again. This is because I struggled with an *invalid instance ID * error on the ssm agent for days bfore I figured out how t odebug it and it now works when it doesn't get confused which instance to take the instance ID from. 


References:
Boto3 mount
https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ebs-using-volumes.html
https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Instance.attach_volume

SSH Key Genration:
https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-key-pairs.html#how-to-generate-your-own-key-and-import-it-to-aws

SSM Agent troubleshooting:
https://stackoverflow.com/questions/47034797/invalidinstanceid-an-error-occurred-invalidinstanceid-when-calling-the-sendco
