import type { DatasetData, DatasetSummary, Direction, SiteData } from "../lib/types";

// Seven hexagons: one at the Queen Victoria Building's coordinates and a ring of six around it.
// Hexagon 0 is ok by train, 1 ok by bus, 2 ok walking only, 3 no journey, 4 walk too far,
// 5 not found, 6 not computed. Hexagons 0-2 and 6 are in Sydney, 3-5 in Haymarket.
export const ONWARD_ID = "TEST_2026-10-12_arr0900";
export const RETURN_ID = "TEST_2026-10-10_dep2100_w3h";
const BASE: [number, number] = [15120669, -3387174];
const R = 200;
const OFFSETS: [number, number][] = [[0, 0], ...Array.from({ length: 6 }, (_, j): [number, number] => {
  const a = Math.PI / 6 + (j * Math.PI) / 3;
  return [Math.round(Math.sqrt(3) * R * Math.cos(a)), Math.round(Math.sqrt(3) * R * Math.sin(a))];
})];
const HEX = Array.from({ length: 6 }, (_, j) => [
  Math.round(R * Math.cos((j * Math.PI) / 3)), Math.round(R * Math.sin((j * Math.PI) / 3)),
]).flat();

function summary(direction: Direction): DatasetSummary {
  const onward = direction === "onward";
  return {
    id: onward ? ONWARD_ID : RETURN_ID,
    direction,
    when: onward ? "9:00 on Mon 12 Oct 2026" : "21:00 on Sat 10 Oct 2026",
    label: onward ? "Test Building · to, arrive by 9:00 · Mon 12 Oct 2026"
      : "Test Building · from, leave at 21:00 (wait up to 3 h) · Sat 10 Oct 2026",
    maxWaitHours: onward ? null : 3,
    building: { name: "Test Building", address: "1 TEST STREET, SYDNEY NSW 2000", xy: BASE },
    counts: {},
    finished: "2026-09-27T07:55:09+10:00",
  };
}

export function fixtureSite(): SiteData {
  return {
    scale: 100_000,
    total: 7,
    localities: ["Haymarket", "Sydney"],
    center: OFFSETS.flatMap(([dx, dy]) => [BASE[0] + dx, BASE[1] + dy]),
    verts: OFFSETS.map(() => [...HEX]),
    loc: [1, 1, 1, 0, 0, 0, 1],
    labels: [["Sydney", BASE[0], BASE[1] + 300, 1]],
    datasets: [summary("onward"), summary("return")],
    transit: {
      lines: { rail: [[BASE[0] - 600, BASE[1], BASE[0] + 600, BASE[1]]] },
      stations: [["Town Hall Station", BASE[0], BASE[1], "rail"]],
    },
  };
}

export function fixtureDataset(direction: Direction): DatasetData {
  const night = direction === "return";
  const data: DatasetData = {
    ...summary(direction),
    status: [1, 1, 1, 2, 4, 3, 0],
    minutes: night ? [40, 200, 130, null, null, null, null] : [25, 50, 140, null, null, null, null],
    walkMin: [6, 12, 3, null, null, null, null],
    walkM: [450, 900, 200, null, null, null, null],
    transports: [1, 2, 0, null, null, null, null],
    modes: [2, 1, 0, 0, 0, 0, 0],
    depart: ["08:20", "07:30", "06:40", "", "", "", ""],
    arrive: ["08:45", "08:20", "09:00", "", "", "", ""],
    address: ["1 TEST STREET, SYDNEY", "2 TEST STREET, SYDNEY", "3 TEST STREET, SYDNEY",
      "4 TEST STREET, HAYMARKET", "5 TEST STREET, HAYMARKET", "6 TEST STREET, HAYMARKET", ""],
    legs: [
      [[0, "", 4, 300, 0, 1], [1, "T1", 15, 9000, 1, 2], [0, "", 6, 450, 2, 0]],
      [[2, "333", 40, 12000, 3, 4]],
      null, null, null, null, null,
    ],
    computed: 6,
    legModes: ["walk", "train", "bus"],
    stops: ["", "Central Station", "Town Hall Station", "Bondi Junction", "Railway Square"],
  };
  if (night) Object.assign(data, {
    trip: [35, 60, 125, null, null, null, null],
    wait: [5, 140, 5, null, null, null, null],
    morning: [0, 1, 0, 0, 0, 0, 0],
  });
  return data;
}
