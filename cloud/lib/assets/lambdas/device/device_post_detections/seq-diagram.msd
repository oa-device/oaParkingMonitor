#//# --------------------------------------------------------------------------------------
#//# Created using Sequence Diagram for Mac
#//# https://www.macsequencediagram.com
#//# https://itunes.apple.com/gb/app/sequence-diagram/id1195426709?mt=12
#//# --------------------------------------------------------------------------------------
# style
# canvasBgColor: FFFFFF
# end # style-reset

title "POST /detections"

participant "Detector" as D
participant "API Gateway\nPOST /detections" as API
participant "Lambda\nauthorizer" as AUTH
participant "Lambda\npost-detection" as PD
participant "dynamodb\ndetections" as DBDetections
participant "dynamodb\nsystem_states" as DBSystem_states


D->API:detections
API->AUTH:detections
AUTH-->API:Allow

API->PD:detections

loop detections

	PD->DBDetections:get(detection.id)
	PD->DBSystem_states:get(last_detections_aggregation)

	alt [ detection doesn't exist ]
		PD->PD: keep detection
		
		alt [ detection.ts < last_detections_aggregation ]
			PD->PD: update last_detections_aggregation
		end
	end

end #detections

PD->DBDetections:put(detections kept)

alt [ last_detections_aggregation changed ]
	PD-> DBSystem_states:put(last_detections_aggregation)
end

