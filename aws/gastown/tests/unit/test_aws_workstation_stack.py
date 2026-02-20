import aws_cdk as core
import aws_cdk.assertions as assertions

from aws_workstation.aws_workstation_stack import AwsWorkstationStack

# example tests. To run these tests, uncomment this file along with the example
# resource in aws_workstation/aws_workstation_stack.py
def test_sqs_queue_created():
    app = core.App()
    stack = AwsWorkstationStack(app, "aws-workstation")
    template = assertions.Template.from_stack(stack)

#     template.has_resource_properties("AWS::SQS::Queue", {
#         "VisibilityTimeout": 300
#     })
