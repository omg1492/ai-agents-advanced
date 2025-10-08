output "deployment_summary" {
  description = "Summary of deployed MCP servers"
  value = {
    farmer_tools = {
      url      = "https://${azapi_resource.farmer_tools.output.properties.configuration.ingress.fqdn}"
      health   = "https://${azapi_resource.farmer_tools.output.properties.configuration.ingress.fqdn}/health"
      replicas = "${var.farmer_tools_min_replicas}-1"
    }
    viz_gen = {
      url      = "https://${azapi_resource.viz_gen.output.properties.configuration.ingress.fqdn}"
      health   = "https://${azapi_resource.viz_gen.output.properties.configuration.ingress.fqdn}/health"
      replicas = "${var.viz_gen_min_replicas}-1"
    }
  }
}
