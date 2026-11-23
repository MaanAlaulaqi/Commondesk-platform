import { defineRailway, project, service } from "railway/iac";

export const partial = "commondesk-health";
export default defineRailway(() => {
  const health = { healthcheck: "/readyz", healthcheckTimeout: 180 };
  return project("satisfied-purpose", {
    variables: { managed: false },
    resources: [service("commondesk-api", health), service("commondesk-worker", health)],
  });
});
