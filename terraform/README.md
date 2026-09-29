# Availability History Tracker on EKS

This Terraform stack creates:

- A two-AZ VPC with private EKS nodes and a single NAT gateway.
- An EKS managed node group.
- The EBS CSI add-on and `gp3` persistent volumes for the backend database and uploads.
- The AWS Load Balancer Controller using an IAM role for service accounts.
- The backend, frontend, and ALB ingress resources from `k8s/`, using the images already configured in that directory.

## Prerequisites

- Terraform >= 1.6
- AWS CLI credentials configured for the target account
- An AWS account with permissions to create VPC, EKS, IAM, EC2, and ELB resources

## Deploy

Run these commands from this directory:

```powershell
terraform init
terraform plan
terraform apply
aws eks update-kubeconfig --region ap-south-1 --name availability-history-tracker
kubectl get nodes
kubectl get pods -A
```

The first apply can take 20-30 minutes. The ALB hostname may remain `pending` briefly after the apply while AWS provisions it:

```powershell
kubectl get ingress availability-ingress
```

Point `availability.local` at the reported ALB hostname in DNS, or add it to your local hosts file for testing. Override settings without editing the files:

```powershell
terraform apply -var="aws_region=ap-south-1" -var="app_host=tracker.example.com"
```

The default node group and NAT gateway incur AWS charges. Run `terraform destroy` when the environment is no longer needed.
