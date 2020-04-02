import boto3
import configparser
import json
import os
import time


def setup_redshift():
    """Sets up the Redshift cluster for use in ETL:
    1. Creates a Redshift IAM role and attaches the S3ReadOnly policy to it.
    2. Creates the Redshift cluster.
    3. Once creation is complete, opens the TCP port for the IPV4_ADDRESS
    as specified.

    The setup relies on the following environment variables to be set:
    AWS_KEY - AWS key for Redshift admin
    AWS_SECRET - AWS secret for Redshift admin
    IPV4_ADDRESS - IPV4 CIDR address for machine that will be interacting
    with the cluster, in the format 0.0.0.0/0
    """
    print('Starting Redshift setup...')

    _check_environment_variables()

    config = _load_config()

    # Create the Redshift IAM role and attach the correct policy
    _prepare_iam_role(config)

    # Create the Redshift cluster
    _create_redshift_cluster(config)

    # Wait until cluster has created
    _wait_redshift_creation(config)

    # Allow access from IP address to connect to database
    _open_redshift_tcp(config)

    with open('../dwh.cfg', 'w') as configfile:
        config.write(configfile)

    print('Redshift setup complete.')


# Raise KeyError if any of these are not set
def _check_environment_variables():
    os.environ['AWS_KEY']
    os.environ['AWS_SECRET']
    os.environ['IPV4_ADDRESS']


def _load_config():
    print('Loading Redshift parameters from config...')

    dir_path = os.path.dirname(os.path.realpath(__file__))
    config_path = dir_path + '/../dwh.cfg'
    config = configparser.ConfigParser()
    config.read(config_path)

    return config


def _prepare_iam_role(config):
    print('Preparing IAM role...')

    iam = boto3.client(
        'iam',
        aws_access_key_id=os.environ['AWS_KEY'],
        aws_secret_access_key=os.environ['AWS_SECRET'],
        region_name=config['REDSHIFT']['REGION']
    )

    iam_role = _create_iam_role(iam, config['IAM']['ROLE_NAME'])
    config['IAM']['REDSHIFT_ARN'] = iam_role['Role']['Arn']

    _attach_iam_policy(iam, config['IAM']['ROLE_NAME'])

    return iam_role


def _attach_iam_policy(iam, iam_role_name):
    print('Attaching IAM policy...')
    try:
        print('Attaching AmazonS3ReadOnlyAccess Policy to IAM Role')
        iam.attach_role_policy(
            RoleName=iam_role_name,
            PolicyArn='arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess'
        )['ResponseMetadata']['HTTPStatusCode']
    except Exception as e:
        print('Error attaching policy:')
        print(e)


def _create_iam_role(iam, iam_role_name):
    print('Creating IAM role...')
    try:
        print('Creating Redshift IAM Role')
        iam_role = iam.create_role(
            Path='/',
            RoleName=iam_role_name,
            Description='Allows Redshift clusters to call AWS services on your behalf.',
            AssumeRolePolicyDocument=json.dumps(
                {'Statement': [{'Action': 'sts:AssumeRole',
                 'Effect': 'Allow',
                 'Principal': {'Service': 'redshift.amazonaws.com'}}],
                 'Version': '2012-10-17'}
            )
        )
    except Exception as e:
        print('Error creating IAM role:')
        print(e)

    return iam_role


def _create_redshift_cluster(config):
    print('Creating Redshift cluster...')
    redshift = boto3.client(
        'redshift',
        region_name=config['REDSHIFT']['REGION'],
        aws_access_key_id=os.environ['AWS_KEY'],
        aws_secret_access_key=os.environ['AWS_SECRET']
    )

    redshift.create_cluster(
        ClusterType=config['REDSHIFT']['CLUSTER_TYPE'],
        NodeType=config['REDSHIFT']['NODE_TYPE'],
        NumberOfNodes=int(config['REDSHIFT']['NUM_NODES']),
        DBName=config['REDSHIFT']['DB_NAME'],
        ClusterIdentifier=config['REDSHIFT']['CLUSTER_IDENTIFIER'],
        MasterUsername=config['REDSHIFT']['DB_USER'],
        MasterUserPassword=config['REDSHIFT']['DB_PASSWORD'],
        IamRoles=[config['IAM']['REDSHIFT_ARN']]
    )


def _wait_redshift_creation(config):
    redshift = boto3.client(
        'redshift',
        region_name=config['REDSHIFT']['REGION'],
        aws_access_key_id=os.environ['AWS_KEY'],
        aws_secret_access_key=os.environ['AWS_SECRET']
    )

    wait_cycles = 0
    while (True):
        cluster_props = redshift.describe_clusters(ClusterIdentifier=config['REDSHIFT']['CLUSTER_IDENTIFIER'])['Clusters'][0]

        if cluster_props['ClusterStatus'] == 'available':
            config['REDSHIFT']['ENDPOINT'] = cluster_props['Endpoint']['Address']
            config['REDSHIFT']['VPC_ID'] = cluster_props['VpcId']
            print('Redshift creation complete.')
            break

        time_to_wait = 60 * 2**(wait_cycles)
        wait_cycles += 1
        print("Waiting %s seconds..." % time_to_wait)
        time.sleep(time_to_wait)


def _open_redshift_tcp(config):
    print('Opening Redshift TCP...')
    ec2 = boto3.resource(
        'ec2',
        region_name=config['REDSHIFT']['REGION'],
        aws_access_key_id=os.environ['AWS_KEY'],
        aws_secret_access_key=os.environ['AWS_SECRET']
    )

    try:
        vpc = ec2.Vpc(id=config['REDSHIFT']['VPC_ID'])
        default_sg = list(vpc.security_groups.all())[0]
        default_sg.authorize_ingress(
            GroupName=default_sg.group_name,
            CidrIp=os.environ['IPV4_ADDRESS'],
            IpProtocol='TCP',
            FromPort=int(config['REDSHIFT']['DB_PORT']),
            ToPort=int(config['REDSHIFT']['DB_PORT'])
        )
    except Exception as e:
        print('Error opening Redshift TCP:')
        print(e)


def main():
    setup_redshift()


if __name__ == '__main__':
    main()
