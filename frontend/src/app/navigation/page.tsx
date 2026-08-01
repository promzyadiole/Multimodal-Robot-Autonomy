"use client";

import { useEffect, useMemo, useState } from "react";
import Topbar from "@/components/topbar";
import {
  getEnvironment,
  getNavigationPlaces,
  goToPlace,
  initializeLocalization,
  type EnvironmentConfig,
  type PlacePose,
} from "@/lib/api";

type PlacesRecord = Record<string, PlacePose>;

function formatPlaceLabel(place: string): string {
  return place
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

function quaternionToYaw(qz: number, qw: number): number {
  return Math.atan2(2 * qw * qz, 1 - 2 * qz * qz);
}

export default function NavigationPage() {
  const [environment, setEnvironment] = useState<EnvironmentConfig | null>(null);
  const [places, setPlaces] = useState<PlacesRecord>({});
  const [selectedPlace, setSelectedPlace] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(true);
  const [busy, setBusy] = useState<boolean>(false);
  const [message, setMessage] = useState<string>("");
  const [failed, setFailed] = useState<boolean>(false);

  useEffect(() => {
    async function load() {
      try {
        setLoading(true);
        const [envRes, placesRes] = await Promise.all([
          getEnvironment(),
          getNavigationPlaces(),
        ]);
        setEnvironment(envRes.data ?? null);
        const loadedPlaces: PlacesRecord = placesRes.data?.places ?? {};
        setPlaces(loadedPlaces);
        const firstPlace = Object.keys(loadedPlaces)[0];
        if (firstPlace) setSelectedPlace(firstPlace);
      } catch (error) {
        setFailed(true);
        setMessage(
          error instanceof Error ? error.message : "Could not load navigation data.",
        );
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const placeOptions = useMemo(() => Object.keys(places), [places]);
  const selectedPose = selectedPlace ? places[selectedPlace] : null;

  async function run(
    fn: () => Promise<{ message?: string }>,
    fallback: string,
  ): Promise<void> {
    try {
      setBusy(true);
      setMessage("");
      setFailed(false);
      const res = await fn();
      setMessage(res.message ?? fallback);
    } catch (error) {
      setFailed(true);
      setMessage(error instanceof Error ? error.message : fallback);
    } finally {
      setBusy(false);
    }
  }

  const nav = environment?.navigation as Record<string, string> | undefined;
  const mapName = nav?.map_yaml_path?.split("/").pop();

  return (
    <div>
      <Topbar
        title="Navigation"
        subtitle="Seed localisation, then send the robot to a named place. Coordinates come from the environment's place registry rather than being typed in."
      />

      {/* Environment as one dense strip of readouts rather than a card of prose. */}
      <section className="mb-8 grid gap-px overflow-hidden rounded-sm border border-rule bg-rule sm:grid-cols-3">
        <Readout label="environment" value={environment?.name ?? (loading ? "…" : "—")} />
        <Readout label="map" value={mapName ?? (loading ? "…" : "—")} />
        <Readout
          label="destinations"
          value={loading ? "…" : String(placeOptions.length)}
        />
      </section>

      <div className="grid gap-8 lg:grid-cols-[1fr_20rem]">
        {/* Destinations carry their coordinates, so the page shows exactly what
            it will send rather than hiding it behind a label. */}
        <section>
          <div className="flex items-baseline justify-between gap-4">
            <h3 className="font-data text-[11px] tracking-[0.2em] text-muted uppercase">
              Destinations
            </h3>
            <button
              type="button"
              onClick={() => run(initializeLocalization, "Localisation initialised.")}
              disabled={busy}
              className="font-data text-[11px] text-scan transition-colors hover:text-scan-hot disabled:text-muted"
            >
              {busy ? "working…" : "initialise localisation →"}
            </button>
          </div>

          {loading ? (
            <p className="mt-6 font-data text-[12px] text-muted">loading places…</p>
          ) : placeOptions.length === 0 ? (
            <p className="mt-6 font-data text-[12px] text-muted">
              no places defined in this environment
            </p>
          ) : (
            <ul className="mt-4 divide-y divide-rule overflow-hidden rounded-sm border border-rule">
              {placeOptions.map((place) => {
                const pose = places[place];
                const active = place === selectedPlace;
                return (
                  <li key={place}>
                    <button
                      type="button"
                      onClick={() => setSelectedPlace(place)}
                      aria-pressed={active}
                      className={`flex w-full items-center gap-4 border-l-2 px-4 py-3.5 text-left transition-colors ${
                        active
                          ? "border-scan bg-panel-2"
                          : "border-transparent bg-panel hover:bg-panel-2"
                      }`}
                    >
                      <span
                        className={`text-[14px] ${active ? "text-ink" : "text-ink-soft"}`}
                      >
                        {formatPlaceLabel(place)}
                      </span>
                      <span className="ml-auto font-data text-[11px] tabular-nums text-muted">
                        {Number(pose.x).toFixed(2)}, {Number(pose.y).toFixed(2)}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </section>

        <aside className="flex flex-col gap-4">
          <div className="rounded-sm border border-rule bg-panel p-5">
            <h3 className="font-data text-[11px] tracking-[0.2em] text-muted uppercase">
              Target pose
            </h3>
            {selectedPose ? (
              <dl className="mt-4 flex flex-col gap-2 font-data text-[12px] tabular-nums">
                <Field k="x" v={Number(selectedPose.x).toFixed(4)} />
                <Field k="y" v={Number(selectedPose.y).toFixed(4)} />
                <Field
                  k="yaw"
                  v={`${quaternionToYaw(
                    Number(selectedPose.qz),
                    Number(selectedPose.qw),
                  ).toFixed(3)} rad`}
                />
                <Field k="frame" v="map" />
              </dl>
            ) : (
              <p className="mt-4 font-data text-[12px] text-muted">pick a destination</p>
            )}
          </div>

          <button
            type="button"
            onClick={() =>
              run(
                () => goToPlace(selectedPlace),
                `Goal sent to ${formatPlaceLabel(selectedPlace)}.`,
              )
            }
            disabled={busy || !selectedPlace}
            className="rounded-sm bg-scan px-5 py-3.5 font-data text-[13px] font-medium tracking-wide text-ground transition-colors hover:bg-scan-hot disabled:cursor-not-allowed disabled:bg-panel-2 disabled:text-muted"
          >
            {busy
              ? "dispatching…"
              : `Go to ${selectedPlace ? formatPlaceLabel(selectedPlace) : "…"}`}
          </button>

          {message ? (
            <p
              role="status"
              className={`border-l-2 py-1 pl-3 text-[12.5px] leading-relaxed ${
                failed ? "border-signal text-signal" : "border-scan text-ink-soft"
              }`}
            >
              {message}
            </p>
          ) : null}

          <p className="text-[12px] leading-relaxed text-muted">
            Dispatch returns as soon as nav2 accepts the goal. To wait for the real
            outcome — and recover if it fails — use Chat, which verifies arrival.
          </p>
        </aside>
      </div>
    </div>
  );
}

function Readout({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-panel px-5 py-4">
      <p className="font-data text-[10px] tracking-[0.18em] text-muted uppercase">
        {label}
      </p>
      <p className="mt-1.5 truncate font-data text-[14px] text-ink">{value}</p>
    </div>
  );
}

function Field({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex items-baseline justify-between gap-4">
      <dt className="text-muted">{k}</dt>
      <dd className="text-ink">{v}</dd>
    </div>
  );
}
