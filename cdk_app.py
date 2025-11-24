#!/usr/bin/env python3
import aws_cdk as cdk
from cdk_stack import ContentTransformerStack

app = cdk.App()
ContentTransformerStack(app, "ContentTransformerStack")
app.synth()