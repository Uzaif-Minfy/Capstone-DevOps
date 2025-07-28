#!/bin/bash

echo "=== DevOps Capstone Monitoring Status ==="
echo "Date: $(date)"
echo ""

# Try multiple methods to get public IP
PUBLIC_IP=$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || curl -s ifconfig.me 2>/dev/null || curl -s ipinfo.io/ip 2>/dev/null || echo "Unable to detect")
echo "Public IP: $PUBLIC_IP"
echo ""

# Check Docker containers
echo "Docker Containers Status:"
docker-compose ps
echo ""

# Check individual services
echo "Service Health Check:"

# Prometheus
if curl -s http://localhost:9090/-/healthy > /dev/null; then
    echo "✅ Prometheus: Running (http://$PUBLIC_IP:9090)"
else
    echo "❌ Prometheus: Down"
fi

# Grafana
if curl -s http://localhost:3000/api/health > /dev/null; then
    echo "✅ Grafana: Running (http://$PUBLIC_IP:3000)"
else
    echo "❌ Grafana: Down"
fi

# Node Exporter
if curl -s http://localhost:9100/metrics > /dev/null; then
    echo "✅ Node Exporter: Running (http://$PUBLIC_IP:9100)"
else
    echo "❌ Node Exporter: Down"
fi

# Blackbox Exporter
if curl -s http://localhost:9115/metrics > /dev/null; then
    echo "✅ Blackbox Exporter: Running (http://$PUBLIC_IP:9115)"
else
    echo "❌ Blackbox Exporter: Down"
fi

# AlertManager
if curl -s http://localhost:9093/-/healthy > /dev/null; then
    echo "✅ AlertManager: Running (http://$PUBLIC_IP:9093)"
else
    echo "❌ AlertManager: Down"
fi

# cAdvisor
if curl -s http://localhost:8080/healthz > /dev/null; then
    echo "✅ cAdvisor: Running (http://$PUBLIC_IP:8080)"
else
    echo "❌ cAdvisor: Down"
fi

echo ""
echo "=== Access URLs ==="
echo "Grafana Dashboard: http://$PUBLIC_IP:3000 (admin/admin123)"
echo "Prometheus: http://$PUBLIC_IP:9090"
echo "AlertManager: http://$PUBLIC_IP:9093"
echo "Node Exporter: http://$PUBLIC_IP:9100"
echo ""
echo "=== Website Monitoring ==="
echo "S3 Website 1: http://minfy-uzaif-capstone-deployments.s3-website.ap-south-1.amazonaws.com/recipe-finder-react/current/"
echo "S3 Website 2: http://minfy-uzaif-capstone-deployments.s3-website.ap-south-1.amazonaws.com/capstone-testing/current/"
echo ""
echo "=== Quick Commands ==="
echo "Check logs: docker-compose logs -f [service_name]"
echo "Restart service: docker-compose restart [service_name]"
echo "Stop all: docker-compose down"
echo "Start all: docker-compose up -d"
