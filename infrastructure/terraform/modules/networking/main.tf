resource "aws_vpc" "this" {
    cidr_block = var.vpc_cidr
    enable_dns_support = true
    enable_dns_hostnames = true

    tags = {
        Name = "${var.project}-${var.env}-vpc"
    }
}

resource "aws_internet_gateway" "this" {
    vpc_id = aws_vpc.this.id 

    tags = {
        Name = "${var.project}-${var.env}-igw"
    }
}

resource "aws_subnet" "public" {
    count = length(var.public_subnet_cidrs)
    vpc_id = aws_vpc.this.id 
    cidr_block = var.public_subnet_cidrs[count.index]
    availability_zone = var.azs[count.index]
    map_public_ip_on_launch = true

    tags = {
        Name = "${var.project}-${var.env}-public-${count.index + 1}"
        Type = "public"
    }
}

resource "aws_subnet" "private" {
    count = length(var.private_subnet_cidrs)
    vpc_id = aws_vpc.this.id
    cidr_block = var.private_subnet_cidrs[count.index]
    availability_zone = var.azs[count.index]

    tags = {
        Name = "${var.project}-${var.env}-private-${count.index + 1}"
        Type = "private"
    }
}

resource "aws_eip" "nat" {
    domain = "vpc"

    tags = {
        Name = "${var.project}-${var.env}-nat-eip"
    }
}

resource "aws_nat_gateway" "this" {
    allocation_id = aws_eip.nat.id
    subnet_id = aws_subnet.public[0].id

    tags = {
        Name = "${var.project}-${var.env}-nat"
    }

    depends_on = [aws_internet_gateway.this]
}

resource "aws_route_table" "public" {
    vpc_id = aws_vpc.this.id

    route {
        cidr_block = "0.0.0.0/0"
        gateway_id = aws_internet_gateway.this.id
    }

    tags = {
        Name = "${var.project}-${var.env}-public-rt"
    }
}

resource "aws_route_table_association" "public" {
    count = length(aws_subnet.public)

    subnet_id = aws_subnet.public[count.index].id
    route_table_id = aws_route_table.public.id
}

resource "aws_route_table" "private" {
    vpc_id = aws_vpc.this.id

    route {
        cidr_block = "0.0.0.0/0"
        nat_gateway_id = aws_nat_gateway.this.id
    }

    tags = {
        Name = "${var.project}-${var.env}-private-rt"
    }
}

resource "aws_route_table_association" "private" {
    count = length(aws_subnet.private)
    
    subnet_id = aws_subnet.private[count.index].id
    route_table_id = aws_route_table.private.id
}

resource "aws_security_group" "eks_nodes" {
    name = "${var.project}-${var.env}-eks-nodes-sg"
    description = "Security group for EKS worker nodes"
    vpc_id = aws_vpc.this.id

    egress {
        description = "Allow all outbound traffic"
        from_port = 0
        to_port = 0
        protocol = "-1"
        cidr_blocks = ["0.0.0.0/0"]
    }

    tags = {
        Name = "${var.project}-${var.env}-eks-nodes-sg"
    }
}

resource "aws_security_group" "redis" {
    name = "${var.project}-${var.env}-redis-sg"
    description = "Allow Redis access only from EKS nodes"
    vpc_id = aws_vpc.this.id

    ingress {
        description = "Redis from EKS nodes"
        from_port = 6379
        to_port = 6379
        protocol = "tcp"
        security_groups = [aws_security_group.eks_nodes.id]
    }

    egress {
        description = "Allow all outbound traffic"
        from_port = 0
        to_port = 0
        protocol = "-1"
        cidr_blocks = ["0.0.0.0/0"]
    }

    tags = {
        Name = "${var.project}-${var.env}-redis-sg"
    }
}

resource "aws_security_group" "alb" {
    name        = "${var.project}-${var.env}-alb-sg"
    description = "Security group for Application Load Balancer"
    vpc_id      = aws_vpc.this.id

    ingress {
        description = "HTTP from internet"
        from_port   = 80
        to_port     = 80
        protocol    = "tcp"
        cidr_blocks = ["0.0.0.0/0"]
    }

    ingress {
        description = "HTTPS from internet"
        from_port   = 443
        to_port     = 443
        protocol    = "tcp"
        cidr_blocks = ["0.0.0.0/0"]
    }

    egress {
        description = "Allow all outbound traffic"
        from_port   = 0
        to_port     = 0
        protocol    = "-1"
        cidr_blocks = ["0.0.0.0/0"]
    }

    tags = {
        Name = "${var.project}-${var.env}-alb-sg"
    }
}

