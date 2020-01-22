import opengl_template
import os
import sys
import traceback

import OpenGL
from OpenGL.GL import *
from OpenGL.GLUT import *
from OpenGL.GLU import *
import math
import time
import numpy
import mido


def hsl_to_rgb(h,s,l):
	q = l * (1.0 + s) * (l < .5) + (l + s - l * s) * (l >= .5)
	p = 2 * l - q
	h = h - numpy.floor(h)
	t = [h + 1.0 / 3.0, h, h - 1.0 / 3.0]
	for ix in range(3):
		t[ix] -= numpy.floor(t[ix])
		t[ix] = ((p + 6 * (q - p) * t[ix]) * (t[ix] < 1.0 / 6.0)
				 + q * (t[ix] >= 1.0 / 6.0) * (t[ix] < 3.0 / 6.0)
				 + (p + 6 * (q - p) * (2.0 / 3.0 - t[ix]) ) * (t[ix] >= 3.0 / 6.0) * (t[ix] < 5.0 / 6.0)
				 + p * (t[ix] >= 5.0 / 6.0))
	return t[0],t[1],t[2]

def hsv_to_rgb(h,s,v):
	f = (h - numpy.floor(h)) * 6.0
	hi = numpy.floor(f)
	f -= hi
	
	p = v * (1 - s)
	q = v * (1 - f * s)
	t = v * (1 - (1 - f) * s)
	
	hi = hi.astype(int)
	r = v * (hi == 0) + q * (hi == 1) + p * (hi == 2) + p * (hi == 3) + t * (hi == 4) + v * (hi == 5)
	g = t * (hi == 0) + v * (hi == 1) + v * (hi == 2) + q * (hi == 3) + p * (hi == 4) + p * (hi == 5)
	b = p * (hi == 0) + p * (hi == 1) + t * (hi == 2) + v * (hi == 3) + v * (hi == 4) + q * (hi == 5)
	
	return r,g,b
	
def twiz(x, sz):
	y = numpy.array(x)
	for i in range(sz):
		y[i::sz] = x[i * len(x) // sz : (i + 1)*len(x)//sz]
	return y

class DrawGLScene:
	def __init__(self):
		self.input_port = mido.open_input('TD-25:TD-25 MIDI 1 28:0')
		self.output_port = mido.open_output('TD-25:TD-25 MIDI 1 28:0')

		self.draw_slices = 1
		self.height = 700
		self.width = 1600
		self.pixel_width = 1

		self.reset()
		self.setBpm(80, 4)

	def reset(self):
		self.stream_t0 = time.time()
		self.frames = 0
		self.last_draw_pos = 0

	def setBpm(self, bpm, subdivisions):
		print("BPM/SUB = ", bpm, subdivisions)
		self.bpm = bpm

		self.secondsPerBeat = 60 / self.bpm		
		self.subdivisions = subdivisions

		self.totalBeats = 8

		self.screenWidthInSeconds = self.secondsPerBeat * self.totalBeats

		frames = self.width / self.pixel_width

		self.screenWidthInFrames = frames

		self.draw_interval = self.screenWidthInSeconds / frames
		self.samplesToDraw = numpy.zeros(self.height)

	def keyPressed(self, *args):
		ESCAPE = 27
		print(args[0])

		# If escape is pressed, kill everything.
		if ord(args[0]) == ESCAPE:
			os._exit(0)

		if args[0] == b"=":
			self.reset()
			self.setBpm(self.bpm + 1, self.subdivisions)
		if args[0] == b"-":
			self.reset()
			self.setBpm(self.bpm - 1, self.subdivisions)

		if args[0] == b"]":
			self.reset()
			self.setBpm(self.bpm, self.subdivisions + 1)
		if args[0] == b"[":
			self.reset()
			self.setBpm(self.bpm, self.subdivisions - 1)

	def __call__(self):
		# Clear The Screen And The Depth Buffer
		glClear(GL_DEPTH_BUFFER_BIT)
		glLoadIdentity()					# Reset The View 
		glClearColor(0,0,0,0)
		glShadeModel(GL_FLAT)
	
		t0 = time.time()
		
		if t0 - self.stream_t0 > self.last_draw_pos + self.draw_interval:
			self.draw()
			self.frames += 1
			self.last_draw_pos += self.draw_interval
			
			glFlush()
		else:
			time.sleep(0.001)

	def getCurSamples(self):
		curSamples = numpy.zeros(self.height)

		noteToRange = {
			36: 1, #Kick
			38: 5, #Snare Head
			40: 5, #Snare Rim
			23: 5, #Snare Brush
			37: 5, #Snare XStick
			48: 7, #Tom 1 Head
			50: 7, #Tom 1 Rim
			45: 6, #Tom 2 Head
			47: 6, #Tom 2 Rim
			43: 4, #Tom 3 Head
			58: 4, #Tom 3 Rim
			46: 10, #HH Open Bow
			26: 10, #HH Open Edge
			42: 10, #HH Closed Bow
			22: 10, #HH Closed edge
			44: 10, #HH Pedal
			49: 12, #Crash 1 Bow
			55: 12, #Crash 1 Edge
			57: 13, #Crash 2 Bow
			52: 13, #Crash 2 Edge
			51: 8, #Ride Bow
			59: 8, #Ride Edge
			53: 8, #Ride Bell
			27: 14, #Aux Head
			28: 14, #Aux Rim
		}

		maxRange = 20

		for msg in self.input_port.iter_pending():
			if msg.type == "note_on":
				if msg.note in noteToRange:
					r = noteToRange[msg.note]
					velocityRatio = .2 + .8 * msg.velocity / 128
					curSamples[r * self.height // maxRange: int((r+velocityRatio) * self.height / maxRange)] = 1.0
				else:
					print("unknown note!", msg.note)

		return curSamples
		
	def getTick(self, subdivisions):
		low, high = (
			((self.draw_interval * self.frames) / self.secondsPerBeat) % 1.0, 
			(self.draw_interval * (self.frames + 1) / self.secondsPerBeat) % 1.0
		)

		if high < low:
			low -= 1

		frameBeatWidth = self.draw_interval / self.secondsPerBeat

		totalOverlap = 0.0

		for subdivision in range(subdivisions):
			beatPos = subdivision / subdivisions
			beatPosHigh = beatPos + frameBeatWidth

			overlapRatio = max(0, min(beatPosHigh, high) - max(beatPos, low)) / frameBeatWidth

			totalOverlap += overlapRatio
		
		return totalOverlap

	def draw(self):
		try:
			#compute some data
			glDrawBuffer(GL_FRONT)
			glPixelStorei(GL_UNPACK_ALIGNMENT, 1)
			glWindowPos2i(0,0)

			# glCopyPixels(self.pixel_width, 0, 1024 - self.pixel_width, self.height, GL_COLOR)
			
			samplesToDraw = self.getCurSamples()
			samplesToDraw = samplesToDraw + (self.samplesToDraw - .1).clip(0, None)

			self.samplesToDraw = samplesToDraw

			visualIntensityBeat = self.getTick(1)
			visualIntensityPrimary = self.getTick(self.subdivisions)

			if self.subdivisions == 4:
				visualIntensitySecondary = self.getTick(6)
			else:
				visualIntensitySecondary = 0.0

			line = numpy.ones(self.height)

			r = line * max(1.0 * visualIntensityBeat, .5 * visualIntensityPrimary)
			g = line * max(1.0 * visualIntensityBeat, .5 * visualIntensityPrimary)
			b = line * max(1.0 * visualIntensityBeat, .5 * visualIntensityPrimary)

			line2 = line * 1
			for i in range(10):
				line2[i::20] = 0.0

			r = numpy.maximum(r, line2 * visualIntensitySecondary * .5)
			g = numpy.maximum(g, line2 * visualIntensitySecondary * .5)
			b = numpy.maximum(b, line2 * visualIntensitySecondary * .5)
			
			r = (samplesToDraw + r).clip(None, 1.0)

			if visualIntensityBeat > .01:
				self.sendNote(note=27, velocity=60)

			for pix in range(self.pixel_width):
				glWindowPos2i(int((self.frames % self.screenWidthInFrames) * self.pixel_width) + pix, 0)
				glDrawPixels(1, len(samplesToDraw), GL_RGB, GL_FLOAT, twiz(numpy.concatenate([r,g,b]),3).astype('<f').tostring())
				
		except Exception as e:
			traceback.print_exc(file=sys.stdout)
			sys.exit(0)

	def sendNote(self, note, velocity=90):
		self.output_port.send(mido.Message('note_on', channel=9, note=note, velocity=velocity))
		self.output_port.send(mido.Message('note_off', channel=9, note=note, velocity=velocity))

opengl_template.opengl_main(DrawGLScene(), False)
