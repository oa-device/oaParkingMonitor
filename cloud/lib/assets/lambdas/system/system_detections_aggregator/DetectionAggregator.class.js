/**
 * @class DetectionAggregator
 * 
 * @classdesc Class aggregating parking detections into time-based bins: hour, day, week, month, year.
 * Hour bins aggregate directly from detections.
 * Higher bins (day, week, month, year) are rolled up from lower bins.
 * If a bin already exists, it is updated with new data. Otherwise, a new bin is created.
 * <br/>
 * <br/>
 * Designed for memory efficiency: only hour bins store detection IDs.
 * Luxon is used to handle timezone-aware binning.
 * <br/>
 *
 * @author Edouard Boily <edouard@orangead.ca>
 * @copyright 2025 Orangead Media Inc.
 * 
 * <br/>
 * 
 * This code belongs to Orangead Media Inc. and is not to be shared or used without permission.
 * 
 */
const { DateTime } = require("luxon");

module.exports = class DetectionAggregator {
    constructor() { }

    /**
     * Main aggregation function.
     * Aggregates an array of detections into bins, then rolls up
     * into day, week, month, and year bins.
     *
     * @function DetectionAggregator#aggregate
     * @param {Array<Object>} detections - Array of raw detection objects. Each detection must contain:
     * <ul>
     *   <li>ts (timestamp in ms)</li>
     *   <li>cameraId: string</li>
     *   <li>customerId: string</li>
     *   <li>siteId: string</li>
     *   <li>zoneId: string</li>
     *   <li>occupiedSpaces: number</li>
     *   <li>totalSpaces: number</li>
     *   <li>timezone: string (IANA timezone)</li>
     *   <li>id: string (unique detection ID)</li>
     * </ul>
     * <br/>
     * <br/>
     * @param {Object} existingBins - Existing bins to update (optional). Should contain:
     * <ul>
     *   <li>hourBins: Array of existing hour bins</li>
     *   <li>dayBins: Array of existing day bins</li>
     *   <li>weekBins: Array of existing week bins</li>
     *   <li>monthBins: Array of existing month bins</li>
     *   <li>yearBins: Array of existing year bins</li>
     * </ul>
     * where a bin is:
     * <ul>
     *   <li>id: string (unique bin ID)</li>
     *   <li>binSize: string ("hour", "day", "week", "month", "year")</li>
     *   <li>cameraId: string</li>
     *   <li>customerId: string</li>
     *   <li>siteId: string</li>
     *   <li>zoneId: string</li>
     *   <li>timezone: string (IANA timezone)</li>
     *   <li>startTs: number (bin start timestamp in ms)</li>
     *   <li>startTsH: string (ISO formatted start time)</li>
     *   <li>endTs: number (bin end timestamp in ms)</li>
     *   <li>endTsH: string (ISO formatted end time)</li>
     *   <li>midTs: number (midpoint timestamp in ms)</li>
     *   <li>midTsH: string (ISO formatted midpoint time)</li>
     *   <li>aggregatedIds: Array of detection IDs (only for hour bins)</li>
     *   <li>aggregatedNumber: number (count of aggregated detections)</li>
     *   <li>sumOccupiedSpaces: number (sum of occupied spaces)</li>
     *   <li>sumTotalSpaces: number (sum of total spaces)</li>
     *   <li>minOccupiedSpaces: number (minimum occupied spaces)</li>
     *   <li>maxOccupiedSpaces: number (maximum occupied spaces)</li>
     *   <li>meanOccupiedSpaces: number (mean occupied spaces)</li>
     *   <li>meanTotalSpaces: number (mean total spaces)</li>
     *   <li>occupationRate: number (meanOccupiedSpaces / meanTotalSpaces)</li>
     *   <li>createdAt: number (timestamp in ms)</li>
     *   <li>updatedAt: number (timestamp in ms)</li>
     * </ul>
     * Note that only hour bins have the property `aggregatedIds` to track individual detection IDs.
     * Higher-level bins (day, week, month, year) do not track individual IDs to save memory.
     * @returns {Object} Modified aggregated bins:
     * <ul>
     *   <li>hourBins: Array of hour bins</li>
     *   <li>dayBins: Array of day bins</li>
     *   <li>weekBins: Array of week bins</li>
     *   <li>monthBins: Array of month bins</li>
     *   <li>yearBins: Array of year bins</li>
     * </ul>
     * @public
     */
    aggregate(detections, existingBins) {
        const hourBins = this._aggregateHourBins(detections, existingBins?.hourBins || []);
        const dayBins = this._rollupBins(hourBins, "day", existingBins?.dayBins || []);
        const weekBins = this._rollupBins(hourBins, "week", existingBins?.weekBins || []);
        const monthBins = this._rollupBins(dayBins, "month", existingBins?.monthBins || []);
        const yearBins = this._rollupBins(monthBins, "year", existingBins?.yearBins || []);

        return { hourBins, dayBins, weekBins, monthBins, yearBins };
    }

    // ---- PRIVATE METHODS ----

    /**
     * Aggregate raw detections into hour bins.
     * Each hour bin tracks individual detection IDs.
     *
     * @private
     * @param {Array<Object>} detections - New detections to aggregate
     * @param {Array<Object>} existingHourBins - Existing hour bins to update (optional)
     * @returns {Array<Object>} Array of hour bins
     */
    _aggregateHourBins(detections, existingHourBins = []) {
        const bins = new Map();

        // Seed bins with existing ones
        for (const bin of existingHourBins) {
            bins.set(this._makeBinKey("hour", bin.cameraId, bin.startTs), bin);
        }

        for (const detection of detections) {
            const dt = DateTime.fromMillis(detection.ts, { zone: detection.timezone });
            const start = dt.startOf("hour");
            const end = dt.endOf("hour");

            const key = this._makeBinKey("hour", detection.cameraId, start.toMillis());

            let bin = bins.get(key);
            if (!bin) {
                // No bin yet → create one
                bin = this._newBin("hour", detection, start, end, detection.timezone, true);
                bins.set(key, bin);
            }

            // Avoid double-counting: only update if not already processed
            if (!bin.aggregatedIds.includes(detection.id)) {
                this._updateBinWithParkingDetection(bin, detection);
            }
        }

        return Array.from(bins.values());
    }


    /**
     * Roll up lower-level bins into higher-level bins (day, week, month, year).
     * Does not track individual detection IDs, only aggregates numeric metrics.
     *
     * @private
     * @param {Array<Object>} lowerBins - Array of bins from lower level
     * @param {string} binSize - "day", "week", "month", or "year"
     * @param {Array<Object>} existingUpperBins - Existing upper-level bins to update (optional)
     * @returns {Array<Object>} Array of rolled-up bins
     */
    _rollupBins(lowerBins, binSize, existingUpperBins = []) {
        const bins = new Map();

        // Seed with existing bins
        for (const bin of existingUpperBins) {
            const key = this._makeBinKey(binSize, bin.cameraId, bin.startTs);
            bins.set(key, bin);
        }

        for (const lowerBin of lowerBins) {
            const dt = DateTime.fromMillis(lowerBin.startTs, { zone: lowerBin.timezone });
            const start = dt.startOf(binSize);
            const end = dt.endOf(binSize);

            const key = this._makeBinKey(binSize, lowerBin.cameraId, start.toMillis());

            let bin = bins.get(key);
            if (!bin) {
                // Create a new parent bin if none exists
                bin = this._newBin(binSize, lowerBin, start, end, lowerBin.timezone, false);
                bins.set(key, bin);
            }

            // Roll the lower bin into the upper bin
            this._updateParkingBinWithBin(bin, lowerBin);
        }

        return Array.from(bins.values());
    }


    /**
     * Generate a unique key for a bin to ensure proper aggregation.
     *
     * @private
     * @param {string} binSize - Size of the bin ("hour", "day", etc.)
     * @param {string} cameraId
     * @param {number} startTs - Bin start timestamp in ms
     * @returns {string} Unique key
     */
    _makeBinKey(binSize, cameraId, startTs) {
        return `${cameraId}_${binSize}_${startTs}`;
    }

    /**
     * Create a new bin object.
     *
     * @private
     * @param {string} binSize - Bin granularity
     * @param {Object} source - Detection or lower-level bin
     * @param {DateTime} start - Start time of bin
     * @param {DateTime} end - End time of bin
     * @param {string} timezone - Timezone string
     * @param {boolean} keepIds - Whether to include aggregatedIds array
     * @returns {Object} Bin object
     */
    _newBin(binSize, source, start, end, timezone, keepIds = false) {
        return {
            id: this._makeBinKey(binSize, source.cameraId, start.toMillis()),
            binSize,
            cameraId: source.cameraId,
            customerId: source.customerId,
            siteId: source.siteId,
            zoneId: source.zoneId,
            timezone,
            startTs: start.toMillis(),
            startTsH: start.toISO(),
            endTs: end.toMillis(),
            endTsH: end.toISO(),
            midTs: start.plus({ milliseconds: (end.toMillis() - start.toMillis()) / 2 }).toMillis(),
            midTsH: start.plus({ milliseconds: (end.toMillis() - start.toMillis()) / 2 }).toISO(),
            aggregatedIds: keepIds ? [] : undefined,
            aggregatedNumber: 0,
            sumOccupiedSpaces: 0,
            sumTotalSpaces: 0,
            // Initialize min/max with null so we can detect empty bins
            minOccupiedSpaces: null,
            maxOccupiedSpaces: null,
            minTotalSpaces: null,
            maxTotalSpaces: null,
            createdAt: Date.now(),
            updatedAt: Date.now(),
        };
    }


    /**
     * Update a bin with a single parking detection.
     *
     * @private
     * @param {Object} bin - The bin to update
     * @param {Object} detection - The parking detection
     */
    _updateBinWithParkingDetection(bin, detection) {
        bin.aggregatedNumber += 1;
        bin.sumOccupiedSpaces += detection.occupiedSpaces;
        bin.sumTotalSpaces += detection.totalSpaces;

        bin.minOccupiedSpaces = bin.minOccupiedSpaces === null
            ? detection.occupiedSpaces
            : Math.min(bin.minOccupiedSpaces, detection.occupiedSpaces);
        bin.maxOccupiedSpaces = bin.maxOccupiedSpaces === null
            ? detection.occupiedSpaces
            : Math.max(bin.maxOccupiedSpaces, detection.occupiedSpaces);
        bin.minTotalSpaces = bin.minTotalSpaces === null
            ? detection.totalSpaces
            : Math.min(bin.minTotalSpaces, detection.totalSpaces);
        bin.maxTotalSpaces = bin.maxTotalSpaces === null
            ? detection.totalSpaces
            : Math.max(bin.maxTotalSpaces, detection.totalSpaces);

        if (bin.aggregatedIds) bin.aggregatedIds.push(detection.id);

        bin.meanOccupiedSpaces = bin.sumOccupiedSpaces / bin.aggregatedNumber;
        bin.meanTotalSpaces = bin.sumTotalSpaces / bin.aggregatedNumber;
        bin.occupationRate = bin.meanOccupiedSpaces / bin.meanTotalSpaces;
        bin.updatedAt = Date.now();
    }


    /**
     * Update a bin with data from a lower-level bin.
     * Only aggregates metrics, does not store IDs.
     *
     * @private
     * @param {Object} bin - The bin to update
     * @param {Object} childBin - The lower-level bin
     */
    _updateParkingBinWithBin(bin, childBin) {
        if (!childBin || childBin.aggregatedNumber === 0) return; // skip empty child bins

        bin.aggregatedNumber += childBin.aggregatedNumber;
        bin.sumOccupiedSpaces += childBin.sumOccupiedSpaces;
        bin.sumTotalSpaces += childBin.sumTotalSpaces;

        bin.minOccupiedSpaces = bin.minOccupiedSpaces === null
            ? childBin.minOccupiedSpaces
            : Math.min(bin.minOccupiedSpaces, childBin.minOccupiedSpaces);
        bin.maxOccupiedSpaces = bin.maxOccupiedSpaces === null
            ? childBin.maxOccupiedSpaces
            : Math.max(bin.maxOccupiedSpaces, childBin.maxOccupiedSpaces);
        bin.minTotalSpaces = bin.minTotalSpaces === null
            ? childBin.minTotalSpaces
            : Math.min(bin.minTotalSpaces, childBin.minTotalSpaces);
        bin.maxTotalSpaces = bin.maxTotalSpaces === null
            ? childBin.maxTotalSpaces
            : Math.max(bin.maxTotalSpaces, childBin.maxTotalSpaces);

        bin.meanOccupiedSpaces = bin.sumOccupiedSpaces / bin.aggregatedNumber;
        bin.meanTotalSpaces = bin.sumTotalSpaces / bin.aggregatedNumber;
        bin.occupationRate = bin.meanOccupiedSpaces / bin.meanTotalSpaces;
        bin.updatedAt = Date.now();
    }
}
// EOF