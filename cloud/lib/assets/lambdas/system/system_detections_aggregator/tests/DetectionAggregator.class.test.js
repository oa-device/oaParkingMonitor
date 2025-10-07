const { DateTime } = require("luxon");
const DetectionAggregator = require("../DetectionAggregator.class");


/**
 * Generate an array of mock detections for testing
 * @param {number} count - number of detections to generate
 * @param {string} cameraId - camera ID for the detections
 * @param {number} startTs - optional starting timestamp (ms since epoch)
 * @param {string} timezone - optional timezone, default 'America/Montreal'
 * @returns {Array} array of detection objects
 */
function generateDetections(count, cameraId, startTs = Date.now(), timezone = "America/Montreal") {
    const detections = [];
    for (let i = 0; i < count; i++) {
        const ts = startTs + i * 5 * 60 * 1000; // 5 minutes apart
        detections.push({
            id: `d${i + 1}`,
            cameraId,
            customerId: "customer1",
            siteId: "site1",
            zoneId: "zone1",
            occupiedSpaces: Math.floor(Math.random() * 5) + 1,
            totalSpaces: 12,
            ts,
            timezone,
        });
    }
    return detections;
}

describe("Basic Aggregator functionality", () => {
    let aggregator;

    beforeEach(() => {
        aggregator = new DetectionAggregator();
    });

    const sampleDetections = [
        {
            id: "d1",
            cameraId: "cam1",
            customerId: "cust1",
            siteId: "site1",
            zoneId: "zone1",
            occupiedSpaces: 2,
            totalSpaces: 12,
            ts: DateTime.fromISO("2025-09-22T15:10:00", { zone: "America/Montreal" }).toMillis(),
            timezone: "America/Montreal",
        },
        {
            id: "d2",
            cameraId: "cam1",
            customerId: "cust1",
            siteId: "site1",
            zoneId: "zone1",
            occupiedSpaces: 4,
            totalSpaces: 12,
            ts: DateTime.fromISO("2025-09-22T15:50:00", { zone: "America/Montreal" }).toMillis(),
            timezone: "America/Montreal",
        },
        {
            id: "d3",
            cameraId: "cam1",
            customerId: "cust1",
            siteId: "site1",
            zoneId: "zone1",
            occupiedSpaces: 3,
            totalSpaces: 12,
            ts: DateTime.fromISO("2025-09-22T16:20:00", { zone: "America/Montreal" }).toMillis(),
            timezone: "America/Montreal",
        },
        {
            id: "d4",
            cameraId: "cam2",
            customerId: "cust1",
            siteId: "site1",
            zoneId: "zone2",
            occupiedSpaces: 1,
            totalSpaces: 8,
            ts: DateTime.fromISO("2025-09-22T15:40:00", { zone: "America/Montreal" }).toMillis(),
            timezone: "America/Montreal",
        }
    ];

    describe("hour aggregation", () => {
        it("aggregates detections correctly by hour and camera", () => {
            const { hourBins } = aggregator.aggregate(sampleDetections);

            expect(hourBins.length).toBe(3); // cam1@15h, cam1@16h, cam2@15h

            // Find bin for cam1@15h
            const cam1_15h = hourBins.find(
                b => b.cameraId === "cam1" && DateTime.fromMillis(b.startTs).hour === 15
            );
            expect(cam1_15h.aggregatedIds).toEqual(["d1", "d2"]);
            expect(cam1_15h.minOccupiedSpaces).toBe(2);
            expect(cam1_15h.maxOccupiedSpaces).toBe(4);
            expect(cam1_15h.sumOccupiedSpaces).toBe(6);
            expect(cam1_15h.meanOccupiedSpaces).toBeCloseTo(3);
            expect(cam1_15h.occupationRate).toBeCloseTo(3 / 12);
        });

        it("creates separate bins for different cameras", () => {
            const { hourBins } = aggregator.aggregate(sampleDetections);

            const cam2_15h = hourBins.find(
                b => b.cameraId === "cam2" && DateTime.fromMillis(b.startTs).hour === 15
            );
            expect(cam2_15h.aggregatedIds).toEqual(["d4"]);
            expect(cam2_15h.sumOccupiedSpaces).toBe(1);
        });
    });

    describe("rollup bins", () => {
        it("rolls up hour bins into day bins", () => {
            const { hourBins, dayBins } = aggregator.aggregate(sampleDetections);

            expect(dayBins.length).toBe(2); // cam1 and cam2
            const cam1Day = dayBins.find(b => b.cameraId === "cam1");
            expect(cam1Day.aggregatedNumber).toBe(3);
            expect(cam1Day.sumOccupiedSpaces).toBe(9);
            expect(cam1Day.minOccupiedSpaces).toBe(2);
            expect(cam1Day.maxOccupiedSpaces).toBe(4);

            const cam2Day = dayBins.find(b => b.cameraId === "cam2");
            expect(cam2Day.aggregatedNumber).toBe(1);
            expect(cam2Day.sumOccupiedSpaces).toBe(1);
        });

        it("rolls up day bins into week/month/year bins", () => {
            const { dayBins, weekBins, monthBins, yearBins } = aggregator.aggregate(sampleDetections);

            // Week rollup
            expect(weekBins.length).toBe(2);
            expect(weekBins.find(b => b.cameraId === "cam1").sumOccupiedSpaces).toBe(9);
            expect(weekBins.find(b => b.cameraId === "cam2").sumOccupiedSpaces).toBe(1);

            // Month rollup
            expect(monthBins.length).toBe(2);
            expect(monthBins.find(b => b.cameraId === "cam1").sumOccupiedSpaces).toBe(9);
            expect(monthBins.find(b => b.cameraId === "cam2").sumOccupiedSpaces).toBe(1);

            // Year rollup
            expect(yearBins.length).toBe(2);
            expect(yearBins.find(b => b.cameraId === "cam1").sumOccupiedSpaces).toBe(9);
            expect(yearBins.find(b => b.cameraId === "cam2").sumOccupiedSpaces).toBe(1);
        });
    });

    describe("bin metrics", () => {
        it("computes meanOccupiedSpaces and occupationRate correctly", () => {
            const { hourBins } = aggregator.aggregate(sampleDetections);
            const bin = hourBins.find(b => b.cameraId === "cam1" && DateTime.fromMillis(b.startTs).hour === 15);
            expect(bin.meanOccupiedSpaces).toBeCloseTo(3);
            expect(bin.meanTotalSpaces).toBe(12);
            expect(bin.occupationRate).toBeCloseTo(3 / 12);
        });
    });
});


describe("Aggregator private methods", () => {
    let aggregator;
    let baseDetection;
    let baseBin;

    beforeEach(() => {
        aggregator = new DetectionAggregator();

        baseDetection = {
            id: "d1",
            cameraId: "cam1",
            customerId: "cust1",
            siteId: "site1",
            zoneId: "zone1",
            occupiedSpaces: 5,
            totalSpaces: 12,
            ts: DateTime.fromISO("2025-09-22T15:10:00", { zone: "America/Montreal" }).toMillis(),
            timezone: "America/Montreal",
        };

        const start = DateTime.fromMillis(baseDetection.ts, { zone: baseDetection.timezone }).startOf("hour");
        const end = DateTime.fromMillis(baseDetection.ts, { zone: baseDetection.timezone }).endOf("hour");

        baseBin = aggregator._newBin("hour", baseDetection, start, end, baseDetection.timezone, true);
    });

    test("_updateBinWithParkingDetection updates metrics correctly", () => {
        aggregator._updateBinWithParkingDetection(baseBin, baseDetection);

        expect(baseBin.aggregatedNumber).toBe(1);
        expect(baseBin.sumOccupiedSpaces).toBe(5);
        expect(baseBin.sumTotalSpaces).toBe(12);
        expect(baseBin.minOccupiedSpaces).toBe(5);
        expect(baseBin.maxOccupiedSpaces).toBe(5);
        expect(baseBin.minTotalSpaces).toBe(12);
        expect(baseBin.maxTotalSpaces).toBe(12);
        expect(baseBin.meanOccupiedSpaces).toBeCloseTo(5);
        expect(baseBin.meanTotalSpaces).toBeCloseTo(12);
        expect(baseBin.occupationRate).toBeCloseTo(5 / 12);
        expect(baseBin.aggregatedIds).toContain(baseDetection.id);
        expect(baseBin.updatedAt).toBeGreaterThan(0);
    });

    test("_updateParkingBinWithBin rolls up correctly from child bin", () => {
        const childBin = {
            ...baseBin,
            aggregatedNumber: 2,
            sumOccupiedSpaces: 10,
            sumTotalSpaces: 24,
            minOccupiedSpaces: 4,
            maxOccupiedSpaces: 6,
            minTotalSpaces: 12,
            maxTotalSpaces: 12,
            meanOccupiedSpaces: 5,
            meanTotalSpaces: 12,
            occupationRate: 5 / 12,
        };

        aggregator._updateParkingBinWithBin(baseBin, childBin);

        expect(baseBin.aggregatedNumber).toBe(2);
        expect(baseBin.sumOccupiedSpaces).toBe(10);
        expect(baseBin.sumTotalSpaces).toBe(24);
        expect(baseBin.minOccupiedSpaces).toBe(4);
        expect(baseBin.maxOccupiedSpaces).toBe(6); // merged min/max
        expect(baseBin.meanOccupiedSpaces).toBeCloseTo(10 / 2);
        expect(baseBin.meanTotalSpaces).toBeCloseTo(24 / 2);
        expect(baseBin.occupationRate).toBeCloseTo(5 / 12);
    });

    test("_newBin creates a proper bin structure", () => {
        const dtStart = DateTime.fromMillis(baseDetection.ts, { zone: baseDetection.timezone }).startOf("hour");
        const dtEnd = DateTime.fromMillis(baseDetection.ts, { zone: baseDetection.timezone }).endOf("hour");
        const newBin = aggregator._newBin("hour", baseDetection, dtStart, dtEnd, baseDetection.timezone, true);

        expect(newBin).toHaveProperty("id");
        expect(newBin.binSize).toBe("hour");
        expect(newBin.cameraId).toBe(baseDetection.cameraId);
        expect(newBin.startTs).toBe(dtStart.toMillis());
        expect(newBin.endTs).toBe(dtEnd.toMillis());
        expect(Array.isArray(newBin.aggregatedIds)).toBe(true);
        expect(newBin.aggregatedIds.length).toBe(0);
    });

    test("_makeBinKey produces consistent keys", () => {
        const key1 = aggregator._makeBinKey("hour", "cam1", 1234567890);
        const key2 = aggregator._makeBinKey("hour", "cam1", 1234567890);
        const key3 = aggregator._makeBinKey("hour", "cam2", 1234567890);

        expect(key1).toBe(key2);
        expect(key1).not.toBe(key3);
    });
});

describe("DetectionAggregator hierarchical aggregation", () => {
    let aggregator;

    beforeEach(() => {
        aggregator = new DetectionAggregator();
    });

    const baseDetections = [
        {
            id: "d1",
            cameraId: "cam1",
            customerId: "cust1",
            siteId: "site1",
            zoneId: "zone1",
            occupiedSpaces: 2,
            totalSpaces: 12,
            ts: DateTime.fromISO("2025-09-22T15:10:00", { zone: "America/Montreal" }).toMillis(),
            timezone: "America/Montreal"
        },
        {
            id: "d2",
            cameraId: "cam1",
            customerId: "cust1",
            siteId: "site1",
            zoneId: "zone1",
            occupiedSpaces: 4,
            totalSpaces: 12,
            ts: DateTime.fromISO("2025-09-22T14:50:00", { zone: "America/Montreal" }).toMillis(),
            timezone: "America/Montreal"
        },
        {
            id: "d3",
            cameraId: "cam1",
            customerId: "cust1",
            siteId: "site1",
            zoneId: "zone1",
            occupiedSpaces: 3,
            totalSpaces: 12,
            ts: DateTime.fromISO("2025-09-22T15:45:00", { zone: "America/Montreal" }).toMillis(),
            timezone: "America/Montreal"
        }
    ];

    test("hour aggregation: aggregates detections correctly by hour and camera", () => {
        const { hourBins } = aggregator.aggregate(baseDetections);

        expect(hourBins.length).toBe(2); // d2 forms previous hour, d1+d3 current hour

        const currentHourBin = hourBins.find(b => b.aggregatedIds.includes("d1"));
        expect(currentHourBin.aggregatedIds.sort()).toEqual(["d1", "d3"].sort());
        expect(currentHourBin.aggregatedNumber).toBe(2);
        expect(currentHourBin.minOccupiedSpaces).toBe(2);
        expect(currentHourBin.maxOccupiedSpaces).toBe(3);
        expect(currentHourBin.meanOccupiedSpaces).toBeCloseTo((2 + 3) / 2);
        expect(currentHourBin.meanTotalSpaces).toBeCloseTo(12);
        expect(currentHourBin.occupationRate).toBeCloseTo((2 + 3) / 2 / 12);
    });

    test("hierarchical rollups: hour → day → month → year", () => {
        const { hourBins, dayBins, weekBins, monthBins, yearBins } = aggregator.aggregate(baseDetections);

        // Day bin
        expect(dayBins.length).toBe(1);
        expect(dayBins[0].aggregatedNumber).toBe(3); // all 3 detections
        expect(dayBins[0].minOccupiedSpaces).toBe(2);
        expect(dayBins[0].maxOccupiedSpaces).toBe(4);

        // Week bin
        expect(weekBins.length).toBe(1);
        expect(weekBins[0].aggregatedNumber).toBe(3);

        // Month bin
        expect(monthBins.length).toBe(1);
        expect(monthBins[0].aggregatedNumber).toBe(3);

        // Year bin
        expect(yearBins.length).toBe(1);
        expect(yearBins[0].aggregatedNumber).toBe(3);
    });

    test("handles out-of-order and late detections correctly", () => {
        const lateDetection = {
            id: "d4",
            cameraId: "cam1",
            customerId: "cust1",
            siteId: "site1",
            zoneId: "zone1",
            occupiedSpaces: 5,
            totalSpaces: 12,
            ts: DateTime.fromISO("2025-09-22T14:30:00", { zone: "America/Montreal" }).toMillis(),
            timezone: "America/Montreal"
        };

        const { hourBins, dayBins } = aggregator.aggregate([...baseDetections, lateDetection]);

        const previousHourBin = hourBins.find(b => b.aggregatedIds.includes("d2") || b.aggregatedIds.includes("d4"));
        expect(previousHourBin.aggregatedIds.sort()).toEqual(["d2", "d4"].sort());
        expect(previousHourBin.aggregatedNumber).toBe(2);

        const currentHourBin = hourBins.find(b => b.aggregatedIds.includes("d1"));
        expect(currentHourBin.aggregatedIds.sort()).toEqual(["d1", "d3"].sort());
        expect(currentHourBin.aggregatedNumber).toBe(2);

        const dayBin = dayBins[0];
        expect(dayBin.aggregatedNumber).toBe(4); // all 4 detections included
    });

});


describe("Aggregator Stress Test: multi-camera, multi-hour, multi-day", () => {
    let aggregator;

    beforeEach(() => {
        aggregator = new DetectionAggregator();
    });

    test("correctly aggregates multi-camera, multi-hour, multi-day with late detections", () => {
        const baseDate = DateTime.fromISO("2025-09-22T00:00:00", { zone: "America/Montreal" });
        const cameras = ["cam1", "cam2"];
        const detections = [];

        // generate detections for 3 days, 3 hours per day, 2 cameras
        for (let dayOffset = 0; dayOffset < 3; dayOffset++) {
            for (let hourOffset = 0; hourOffset < 3; hourOffset++) {
                for (const cam of cameras) {
                    const ts = baseDate.plus({ days: dayOffset, hours: hourOffset }).toMillis();
                    detections.push({
                        id: `${cam}-${dayOffset}-${hourOffset}-a`,
                        cameraId: cam,
                        customerId: "cust1",
                        siteId: "site1",
                        zoneId: "zone1",
                        occupiedSpaces: 2 + hourOffset,
                        totalSpaces: 12,
                        ts,
                        timezone: "America/Montreal",
                    });
                    // add late detection in previous hour
                    if (hourOffset > 0) {
                        detections.push({
                            id: `${cam}-${dayOffset}-${hourOffset}-late`,
                            cameraId: cam,
                            customerId: "cust1",
                            siteId: "site1",
                            zoneId: "zone1",
                            occupiedSpaces: 1 + hourOffset,
                            totalSpaces: 12,
                            ts: ts - 60 * 60 * 1000, // 1 hour before
                            timezone: "America/Montreal",
                        });
                    }
                }
            }
        }

        const cam1Detections = generateDetections(15, "cam1");
        const cam2Detections = generateDetections(20, "cam2"); // could be same number too

        const aggregator = new DetectionAggregator();
        const allDetections = [...cam1Detections, ...cam2Detections];
        const { yearBins } = aggregator.aggregate(allDetections);
        const { hourBins, dayBins, weekBins, monthBins } = aggregator.aggregate(detections);

        // --- Multi-camera separation ---
        const cam1YearBin = yearBins.find(b => b.cameraId === "cam1");
        const cam2YearBin = yearBins.find(b => b.cameraId === "cam2");

        // --- Hour bins ---
        expect(hourBins.length).toBeGreaterThanOrEqual(12); // 3 days * 3 hours * 2 cameras, plus late detections
        hourBins.forEach(bin => {
            expect(bin.aggregatedNumber).toBeGreaterThan(0);
            expect(bin.meanOccupiedSpaces).toBeGreaterThan(0);
            expect(bin.minOccupiedSpaces).toBeLessThanOrEqual(bin.maxOccupiedSpaces);
        });

        // --- Day bins ---
        expect(dayBins.length).toBe(3 * 2); // 3 days * 2 cameras
        dayBins.forEach(bin => {
            expect(bin.aggregatedNumber).toBeGreaterThan(0);
            expect(bin.meanOccupiedSpaces).toBeGreaterThan(0);
        });

        // --- Week, Month, Year bins ---
        expect(weekBins.length).toBe(2); // all days per camera rolled into a week
        expect(monthBins.length).toBe(2); // all days per camera rolled into a month
        expect(yearBins.length).toBe(2); // all days per camera rolled into a year

        // Now you can safely reference cam1Detections.length
        expect(cam1YearBin.cameraId).toBe("cam1");
        expect(cam2YearBin.cameraId).toBe("cam2");
        expect(cam1YearBin.aggregatedNumber).toBe(cam1Detections.length);
        expect(cam2YearBin.aggregatedNumber).toBe(cam2Detections.length);
    });
});

describe("Aggregator Full Stress Test: multi-month, multi-timezone, multi-camera", () => {
    let aggregator;

    beforeEach(() => {
        aggregator = new DetectionAggregator();
    });

    test("aggregates detections across months, cameras, and time zones with late arrivals", () => {
        const cameras = ["cam1", "cam2", "cam3"];
        const timezones = ["America/Montreal", "Europe/Paris", "Asia/Tokyo"];
        const detections = [];

        // Map each camera to a fixed timezone
        const cameraTimezones = {};
        cameras.forEach((cam, i) => {
            cameraTimezones[cam] = timezones[i % timezones.length];
        });

        const startDate = DateTime.fromISO("2025-01-01T00:00:00", { zone: "UTC" });

        for (let i = 0; i < 200; i++) {
            // Pick a random camera
            const cam = cameras[Math.floor(Math.random() * cameras.length)];
            const tz = cameraTimezones[cam]; // fixed per camera

            // Random timestamp within first 90 days of 2025
            const ts = startDate
                .plus({
                    days: Math.floor(Math.random() * 90),
                    hours: Math.floor(Math.random() * 24),
                    minutes: Math.floor(Math.random() * 60),
                })
                .toMillis();

            detections.push({
                id: `det-${i}`,
                cameraId: cam,
                customerId: "cust1",
                siteId: "site1",
                zoneId: "zone1",
                occupiedSpaces: Math.floor(Math.random() * 12),
                totalSpaces: 12,
                ts,
                timezone: tz,
            });

            // Occasionally add a late/out-of-order detection
            if (Math.random() < 0.2) {
                const lateTs = ts - Math.floor(Math.random() * 6) * 60 * 60 * 1000; // up to 6h earlier
                detections.push({
                    id: `det-late-${i}`,
                    cameraId: cam,
                    customerId: "cust1",
                    siteId: "site1",
                    zoneId: "zone1",
                    occupiedSpaces: Math.floor(Math.random() * 12),
                    totalSpaces: 12,
                    ts: lateTs,
                    timezone: tz, // still fixed
                });
            }
        }

        const { hourBins, dayBins, weekBins, monthBins, yearBins } = aggregator.aggregate(detections);

        // --- Basic sanity checks ---
        expect(hourBins.length).toBeGreaterThan(0);
        expect(dayBins.length).toBeGreaterThan(0);
        expect(weekBins.length).toBeGreaterThan(0);
        expect(monthBins.length).toBeGreaterThan(0);
        expect(yearBins.length).toBeGreaterThan(0);

        // --- Stats checks ---
        [hourBins, dayBins, weekBins, monthBins, yearBins].forEach(levelBins => {
            levelBins.forEach(bin => {
                expect(bin.aggregatedNumber).toBeGreaterThan(0);
                expect(bin.meanOccupiedSpaces).toBeGreaterThanOrEqual(0);
                expect(bin.minOccupiedSpaces).toBeLessThanOrEqual(bin.maxOccupiedSpaces);
                expect(bin.minTotalSpaces).toBeLessThanOrEqual(bin.maxTotalSpaces);
            });
        });

        // --- Multi-camera separation ---
        cameras.forEach(cam => {
            const camYearBin = yearBins.find(b => b.cameraId === cam);
            expect(camYearBin).toBeDefined();
            expect(camYearBin.aggregatedNumber).toBeGreaterThan(0);
        });

        // --- Ensure rollup consistency ---
        dayBins.forEach(dayBin => {
            const camTz = cameraTimezones[dayBin.cameraId];
            const dayMonth = DateTime.fromMillis(dayBin.startTs, { zone: camTz }).month;

            const monthBin = monthBins.find(
                m =>
                    m.cameraId === dayBin.cameraId &&
                    DateTime.fromMillis(m.startTs, { zone: camTz }).month === dayMonth
            );

            expect(monthBin).toBeDefined();
            expect(monthBin.sumOccupiedSpaces).toBeGreaterThanOrEqual(dayBin.sumOccupiedSpaces);
        });

        weekBins.forEach(weekBin => {
            const camTz = cameraTimezones[weekBin.cameraId];
            const weekYear = DateTime.fromMillis(weekBin.startTs, { zone: camTz }).year;

            const yearBin = yearBins.find(y => y.cameraId === weekBin.cameraId);
            expect(yearBin).toBeDefined();
            expect(yearBin.sumOccupiedSpaces).toBeGreaterThanOrEqual(weekBin.sumOccupiedSpaces);
        });
    });
});

describe("Aggregator Performance Benchmark", () => {
    let aggregator;

    beforeEach(() => {
        aggregator = new DetectionAggregator();
    });

    test("aggregates 10,000+ detections in a reasonable time", () => {
        const numDetections = 15000; // simulate 15k detections
        const cameras = ["cam1", "cam2", "cam3", "cam4"];
        const timezones = ["America/Montreal", "Europe/Paris", "Asia/Tokyo"];
        const detections = [];

        const startDate = DateTime.fromISO("2025-01-01T00:00:00", { zone: "UTC" });

        for (let i = 0; i < numDetections; i++) {
            const cam = cameras[Math.floor(Math.random() * cameras.length)];
            const tz = timezones[Math.floor(Math.random() * timezones.length)];
            const ts = startDate.plus({
                days: Math.floor(Math.random() * 90),
                hours: Math.floor(Math.random() * 24),
                minutes: Math.floor(Math.random() * 60),
                seconds: Math.floor(Math.random() * 60),
            }).toMillis();

            detections.push({
                id: `det-${i}`,
                cameraId: cam,
                customerId: "cust1",
                siteId: "site1",
                zoneId: "zone1",
                occupiedSpaces: Math.floor(Math.random() * 12),
                totalSpaces: 12,
                ts,
                timezone: tz,
            });

            // occasionally add late/out-of-order detections
            if (Math.random() < 0.1) {
                const lateTs = ts - Math.floor(Math.random() * 12) * 60 * 60 * 1000; // up to 12 hours earlier
                detections.push({
                    id: `det-late-${i}`,
                    cameraId: cam,
                    customerId: "cust1",
                    siteId: "site1",
                    zoneId: "zone1",
                    occupiedSpaces: Math.floor(Math.random() * 12),
                    totalSpaces: 12,
                    ts: lateTs,
                    timezone: tz,
                });
            }
        }

        const start = Date.now();
        const result = aggregator.aggregate(detections);
        const end = Date.now();

        console.log(`Aggregated ${detections.length} detections in ${end - start} ms`);

        // Optional: verify top-level bin counts are reasonable
        expect(result.hourBins.length).toBeGreaterThan(0);
        expect(result.dayBins.length).toBeGreaterThan(0);
        expect(result.monthBins.length).toBeGreaterThan(0);
        expect(result.yearBins.length).toBeGreaterThan(0);

        // Optional: ensure no negative counts
        Object.values(result).forEach(bins => {
            bins.forEach(bin => {
                expect(bin.aggregatedNumber).toBeGreaterThan(0);
                expect(bin.sumOccupiedSpaces).toBeGreaterThanOrEqual(0);
            });
        });
    });

    test("adds new detections into already existing bins instead of duplicating", () => {
        const aggregator = new DetectionAggregator();

        const baseTs = DateTime.fromISO("2025-01-01T10:15:00", { zone: "America/Montreal" }).toMillis();

        // --- First batch of detections ---
        const detectionsBatch1 = [
            {
                id: "d1",
                cameraId: "cam1",
                customerId: "cust1",
                siteId: "site1",
                zoneId: "zone1",
                occupiedSpaces: 3,
                totalSpaces: 10,
                ts: baseTs,
                timezone: "America/Montreal",
            }
        ];

        let { hourBins } = aggregator.aggregate(detectionsBatch1);

        expect(hourBins.length).toBe(1);
        const firstBin = hourBins[0];
        expect(firstBin.aggregatedNumber).toBe(1);
        expect(firstBin.sumOccupiedSpaces).toBe(3);

        // --- Second batch: new detection in same hour ---
        const detectionsBatch2 = [
            {
                id: "d2",
                cameraId: "cam1",
                customerId: "cust1",
                siteId: "site1",
                zoneId: "zone1",
                occupiedSpaces: 5,
                totalSpaces: 10,
                ts: baseTs + 5 * 60 * 1000, // 5 minutes later, still same hour
                timezone: "America/Montreal",
            }
        ];

        const { hourBins: mergedHourBins } = aggregator.aggregate(detectionsBatch2, { hourBins });

        // Should still be ONE bin, not duplicated
        expect(mergedHourBins.length).toBe(1);

        const mergedBin = mergedHourBins[0];
        expect(mergedBin.aggregatedNumber).toBe(2);
        expect(mergedBin.sumOccupiedSpaces).toBe(8); // 3 + 5
        expect(mergedBin.meanOccupiedSpaces).toBeCloseTo(4);
        expect(mergedBin.aggregatedIds).toContain("d1");
        expect(mergedBin.aggregatedIds).toContain("d2");
    });
});
