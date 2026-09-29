variable "aws_region" {
  description = "AWS region in which to create the EKS cluster."
  type        = string
  default     = "ap-south-1"
}

variable "cluster_name" {
  description = "Name of the EKS cluster."
  type        = string
  default     = "availability-history-tracker"
}

variable "kubernetes_version" {
  description = "Kubernetes version supported by EKS in the selected region."
  type        = string
  default     = "1.33"
}

variable "availability_zones" {
  description = "Availability zones used by the VPC."
  type        = list(string)
  default     = ["ap-south-1a", "ap-south-1b"]
}

variable "node_instance_types" {
  description = "EC2 instance types for the managed node group."
  type        = list(string)
  default     = ["t3.medium"]
}

variable "node_min_size" {
  type    = number
  default = 1
}

variable "node_desired_size" {
  type    = number
  default = 2
}

variable "node_max_size" {
  type    = number
  default = 3
}

variable "app_host" {
  description = "Host used by the ingress. Add the ALB address to DNS or your hosts file."
  type        = string
  default     = "availability.local"
}

variable "frontend_image" {
  type    = string
  default = "sun123testdoc/availability-frontend:latest"
}

variable "backend_image" {
  type    = string
  default = "sun123testdoc/availability-backend:latest"
}
