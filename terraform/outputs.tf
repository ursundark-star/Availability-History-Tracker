output "cluster_name" {
  description = "EKS cluster name for kubectl configuration."
  value       = module.eks.cluster_name
}

output "cluster_endpoint" {
  value = module.eks.cluster_endpoint
}

output "configure_kubectl" {
  value = "aws eks update-kubeconfig --region ${var.aws_region} --name ${module.eks.cluster_name}"
}

output "application_url" {
  description = "Add the ALB hostname to DNS or your hosts file for this hostname."
  value       = "http://${var.app_host}"
}

output "load_balancer_hostname" {
  description = "ALB hostname after the ingress controller provisions it."
  value       = try(kubernetes_ingress_v1.app.status[0].load_balancer[0].ingress[0].hostname, "pending")
}
