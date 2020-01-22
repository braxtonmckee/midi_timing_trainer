import mido

print(mido.get_input_names())

input_port = mido.open_input('TD-25:TD-25 MIDI 1 28:0')
output_port = mido.open_output('TD-25:TD-25 MIDI 1 28:0')

rim_shot = 37

note = 0
for msg in input_port:
	print("RECV", msg)
	if msg.type == "note_on":
		note = (note + 1) % 127
		print("NOTE=", note)
		output_port.send(mido.Message('note_on', channel=9, note=note, velocity=90))
		output_port.send(mido.Message('note_off', channel=9, note=note, velocity=90))
