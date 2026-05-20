import { buildRoadmap } from "../domain/roadmapBuilder.js";
import { catalog, demoProfiles } from "./mockCatalog.js";

export class RoadmapRepository {
  getDemoProfiles() {
    return demoProfiles;
  }

  getRoadmap(profileKey = "programming") {
    const profile = demoProfiles[profileKey] ?? demoProfiles.programming;
    return buildRoadmap(profile, catalog);
  }
}
