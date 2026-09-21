// world-atlas ships TopoJSON data files with no types. Declaring the module
// keeps TypeScript from inferring a type for every coordinate in the file.
declare module "world-atlas/land-110m.json" {
  import type { Topology } from "topojson-specification";

  const topology: Topology;
  export default topology;
}
