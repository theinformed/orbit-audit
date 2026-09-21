import { expect, test } from "@playwright/test";

/**
 * EVERY DRAWN SPACECRAFT HAS TO BE INSIDE THE PICTURE.
 *
 * The opening frame is chosen by `sceneRadiusForActiveLayers()`. Until
 * 2026-08-26 that function measured the magnetosphere, the solar wind, the
 * X-ray tint, the plasmasphere, the ring current, the field lines and the
 * plasma-field cuts — and no spacecraft at all. Its floor was
 * `DEFAULT_VIEW_SCENE_RADIUS`, a 600 km shell, which is LEO. So the site
 * opened framed for the lowest thing it draws, and any fleet above LEO was
 * drawn outside its own picture.
 *
 * Sean, on the shipped build, with MUOS as the constellation of the day: *"So
 * today's satellite constellation of the day is MUOS. But when I load the
 * site, I don't see the constellation."* Three of the five were off screen and
 * two clipped a corner. It is not a MUOS defect — GPS put most of its 40
 * outside the frame in the same build — and it went unnoticed because the
 * rotation had been opening on Iridium, which is LEO, and Iridium fits.
 *
 * A unit test cannot see any of that: the numbers it would check were all
 * correct, and the camera was framing exactly what it had been asked to frame.
 * So this asserts the thing the visitor relies on — a marker's position in the
 * frame — by projecting every drawn marker through the production camera.
 *
 * NEGATIVE CONTROL. Run this file against the commit before the fix and the
 * MEO, GEO and HEO cases fail with markers outside NDC; the LEO case passes
 * there and here, which is what identifies the defect as "the frame is sized
 * for LEO" rather than "the projection is broken".
 */
// The origin is a parameter so the NEGATIVE CONTROL above is runnable: the
// same file is pointed at a second dev server serving the commit before the
// fix, without a copy of it drifting from this one. Defaults to the port
// this project's scratch Playwright config serves.
const harness = `${process.env.SPACE_HARNESS_ORIGIN ?? "http://127.0.0.1:4174"}/tests/satellite-framing.harness.html`;

interface Marker { index: number; x: number; y: number; z: number; sceneRadius: number }
interface CameraState {
  distance: number;
  maxDistance: number;
  aspect: number;
  sceneRadius: number;
  up: number[];
  position: number[];
}

/** A fleet spread around Earth at one altitude, the shape of a real constellation. */
function shell(count: number, altitudeKm: number, inclinationDeg: number) {
  return Array.from({ length: count }, (_, index) => ({
    latitudeDeg: inclinationDeg * Math.sin((index / count) * 2 * Math.PI),
    longitudeDeg: -180 + (360 * index) / count,
    altitudeKm,
  }));
}

async function draw(page: import("@playwright/test").Page, members: Array<{ latitudeDeg: number; longitudeDeg: number; altitudeKm: number }>) {
  // Re-asserted before every fleet rather than once at the top. This harness is
  // served by the dev server, and on a working tree where another session is
  // editing `src/` the module graph can be pushed a full reload mid-run, which
  // takes `window.framingProbe` with it. Waiting here turns that into an
  // ordinary wait instead of a TypeError that reads like a product defect.
  await page.waitForFunction("window.framingProbeReady === true", null, { timeout: 120_000 });
  await page.evaluate(
    (fleet) => (window as unknown as Record<string, any>).framingProbe.drawFleet(fleet),
    members,
  );
  // The re-framing move is a 520 ms ease. Wait for the camera the site
  // actually arrives at — the dolly clears itself on its last frame — rather
  // than for a fixed duration, so a slow software-WebGL machine cannot read a
  // camera still in flight and call it a defect.
  await page.waitForFunction(
    () => (window as unknown as Record<string, any>).framingProbe.dollyActive() === false,
    null,
    { timeout: 30_000 },
  );
  const markers = await page.evaluate(() => (window as unknown as Record<string, any>).framingProbe.drawnMarkers()) as Marker[];
  const camera = await page.evaluate(() => (window as unknown as Record<string, any>).framingProbe.cameraState()) as CameraState;
  return { markers, camera };
}

test.describe("satellite framing", () => {
  test("frames every drawn fleet, at every orbit class", async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.goto(harness);
    await page.waitForFunction("window.framingProbeReady === true", null, { timeout: 120_000 });

    const bare = await page.evaluate(() => (window as unknown as Record<string, any>).framingProbe.cameraState()) as CameraState;

    const fleets = [
      { name: "LEO — an Iridium-shaped shell at 780 km", members: shell(31, 780, 86) },
      { name: "MEO — a GPS-shaped shell at 20,200 km", members: shell(24, 20_200, 55) },
      { name: "GEO — a MUOS-shaped belt at 35,786 km", members: shell(5, 35_786, 3) },
      {
        // A Molniya fleet caught mid-revolution: some near perigee, some near
        // apogee, which is the state that makes "all of them visible" a real
        // question rather than a restatement of one altitude.
        name: "HEO — a Molniya fleet spread from perigee to apogee",
        members: [600, 8_000, 19_000, 30_000, 37_000, 39_900].map((altitudeKm, index) => ({
          latitudeDeg: 63.4 * Math.sin((index / 6) * 2 * Math.PI),
          longitudeDeg: -180 + index * 60,
          altitudeKm,
        })),
      },
    ];

    const distances = new Map<string, number>();
    const framedFrom = (name: string) => {
      const distance = distances.get(name);
      expect(distance, `${name} was never framed, so nothing here can be compared`).toBeDefined();
      return distance!;
    };
    for (const fleet of fleets) {
      const { markers, camera } = await draw(page, fleet.members);
      expect(markers.length, `${fleet.name}: nothing was drawn, so nothing was proved`).toBe(fleet.members.length);
      distances.set(fleet.name, camera.distance);
      for (const marker of markers) {
        expect(
          Math.max(Math.abs(marker.x), Math.abs(marker.y)),
          `${fleet.name}: spacecraft ${marker.index} at scene radius ${marker.sceneRadius.toFixed(1)} `
          + `is outside the frame at NDC (${marker.x.toFixed(2)}, ${marker.y.toFixed(2)}); `
          + `the camera is ${camera.distance.toFixed(0)} out and framing a radius of ${camera.sceneRadius.toFixed(1)}`,
        ).toBeLessThanOrEqual(1);
        // And in front of the far plane, which is the other way a marker
        // vanishes from a scene whose deepest orbits reach 693 scene units.
        expect(marker.z, `${fleet.name}: spacecraft ${marker.index} is outside the depth range`).toBeLessThan(1);
      }
      // The margin is real, not a coincidence of rounding: the framing leaves
      // VIEW_EDGE_MARGIN_FRACTION clear on each edge of the short side.
      const worst = Math.max(...markers.map((marker) => Math.max(Math.abs(marker.x), Math.abs(marker.y))));
      expect(worst, `${fleet.name}: the fleet reaches the very edge of the frame`).toBeLessThan(0.98);
    }

    // AND THE FRAME FOLLOWS THE SUBJECT — it does not simply always sit far
    // out. A LEO-only view is still a LEO-scale view: the whole point of
    // measuring the drawn geometry rather than opening wide enough for
    // anything is that the Earth stays the size of the subject.
    const leo = framedFrom("LEO — an Iridium-shaped shell at 780 km");
    const meo = framedFrom("MEO — a GPS-shaped shell at 20,200 km");
    const geo = framedFrom("GEO — a MUOS-shaped belt at 35,786 km");
    expect(leo, "a LEO fleet was framed from as far back as a GEO one").toBeLessThan(geo * 0.75);
    expect(leo, "a LEO fleet pushed the camera well past the bare-globe opening view")
      .toBeLessThan(bare.distance * 1.15);
    expect(meo, "MEO was not framed further out than LEO").toBeGreaterThan(leo);

    // THE READER'S OWN SELECTION, not only the constellation of the day.
    // Every entry point resolves to `setVisible`, so switching back to a low
    // fleet after a high one has to come back in, or the reader who narrows
    // from GEO to LEO is left staring at a small Earth.
    const { camera: backToLeo } = await draw(page, shell(31, 780, 86));
    expect(
      backToLeo.distance,
      "narrowing from a GEO fleet to a LEO fleet left the camera out at the GEO framing",
    ).toBeLessThan(geo * 0.75);

    expect(errors, "the harness logged page errors").toEqual([]);
  });

  /**
   * THE DEEPEST ORBIT IN THE CATALOGUE, which is the case that decides whether
   * "fit the drawn spacecraft" is affordable at all.
   *
   * TESS reaches 362,765 km. The shared radial ruler compresses that to 693
   * scene units — LESS than the magnetotail the camera is already sized for —
   * so it frames from 2,121 on a desktop, inside the 2,500 dolly limit, with
   * the Earth still 12.9% of the frame's height. That is the same legibility
   * the boundary layers were already accepted at, which is why the satellite
   * reach needs no cap and no per-orbit-class table.
   *
   * On a phone the same fit costs 3,897 units against that 2,500 limit, so the
   * deepest sets frame against the limit instead. That limit is deliberate and
   * predates this work — the constructor in `globe.ts` says why a phone frames
   * the outer magnetosphere against it rather than shrink the Earth to
   * nothing — so this states the phone's honest answer rather than hiding it,
   * and asserts the desktop claim where the site makes it.
   */
  test("frames the deepest catalogued orbits without reaching the dolly limit", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "desktop", "The deepest orbits frame against the phone's dolly limit by design.");
    await page.goto(harness);
    await page.waitForFunction("window.framingProbeReady === true", null, { timeout: 120_000 });
    const { markers: deep, camera: deepCamera } = await draw(page, [
      { latitudeDeg: 10, longitudeDeg: 0, altitudeKm: 362_765 },
      { latitudeDeg: -20, longitudeDeg: 120, altitudeKm: 172_919 },
      { latitudeDeg: 40, longitudeDeg: -120, altitudeKm: 600 },
    ]);
    expect(deepCamera.distance, "the deepest catalogued orbit framed against the dolly limit on a desktop")
      .toBeLessThan(deepCamera.maxDistance);
    for (const marker of deep) {
      expect(
        Math.max(Math.abs(marker.x), Math.abs(marker.y)),
        `deep-space fleet: spacecraft ${marker.index} at scene radius ${marker.sceneRadius.toFixed(1)} is outside the frame`,
      ).toBeLessThanOrEqual(1);
    }
  });

  /**
   * A LAYER MAKES ROOM; IT NEVER TAKES THE WHEEL.
   *
   * Sean: *"When we put the plasma sheet and ring current on, the projection
   * changes to polar. And it makes navigating really difficult."* Four layer
   * toggles used to answer their own switch by flying the camera to a preset.
   * They now all go through `frameActiveLayers`, whose whole contract is that
   * it dollies along the direction the reader is already looking.
   *
   * This pins that contract at the globe: put the camera somewhere deliberate,
   * switch a layer on that needs more room than the view has, and the camera
   * must be further out along the SAME line, with the same up vector.
   */
  test("re-framing for a layer keeps the reader's viewpoint", async ({ page }) => {
    await page.goto(harness);
    await page.waitForFunction("window.framingProbeReady === true", null, { timeout: 120_000 });

    const before = await page.evaluate(() => {
      const probe = (window as unknown as Record<string, any>).framingProbe;
      probe.placeCamera([220, 130, -170]);
      return probe.cameraState();
    }) as CameraState;

    const after = await page.evaluate(() => {
      const probe = (window as unknown as Record<string, any>).framingProbe;
      // The belts reach eight Earth radii on the shared ruler, well past
      // anything a bare globe is framed for, so this toggle genuinely needs
      // the camera to move.
      probe.setLayer("radiation", true);
      probe.frame();
      return probe.cameraState();
    }) as CameraState;

    expect(after.sceneRadius, "the layer did not change what has to fit").toBeGreaterThan(before.sceneRadius);

    const direction = (state: CameraState) => {
      const length = Math.hypot(state.position[0]!, state.position[1]!, state.position[2]!);
      return state.position.map((component) => component / length);
    };
    const beforeDirection = direction(before);
    const afterDirection = direction(after);
    const dot = beforeDirection.reduce((sum, component, index) => sum + component * afterDirection[index]!, 0);
    expect(dot, "switching a layer on rotated the camera instead of pulling it back").toBeGreaterThan(0.9999);
    expect(after.up, "switching a layer on changed which way is up").toEqual(before.up);
  });
});
