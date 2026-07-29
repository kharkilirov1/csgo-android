# It looks like shit, but I'm not particularly worried about such scripts.

import os
import re

token_list = [
	re.compile(r'&&'),
	re.compile(r'\|\|'),
	re.compile(r'\!'),
	re.compile(r'[a-zA-Z0-9_.]*')
]

match_statement = re.compile(r'\[.*\]')

def compute_statement( defines, statement ):
	vars = set(define.split('=')[0] for define in defines)
	expression = re.sub(r'^\[|\]$', '', statement.strip()).replace('$', '')
	tokens = re.findall(r'&&|\|\||!|\(|\)|[A-Za-z0-9_.]+', expression)
	compact = re.sub(r'\s+', '', expression)
	if ''.join(tokens) != compact:
		raise ValueError('Unsupported VPC condition: %s' % statement)

	pos = [0]

	def accept(value):
		if pos[0] < len(tokens) and tokens[pos[0]] == value:
			pos[0] += 1
			return True
		return False

	def primary():
		if accept('('):
			value = logical_or()
			if not accept(')'):
				raise ValueError('Unclosed VPC condition: %s' % statement)
			return value
		if pos[0] >= len(tokens):
			raise ValueError('Missing value in VPC condition: %s' % statement)
		value = tokens[pos[0]]
		pos[0] += 1
		if value == '1':
			return True
		if value == '0':
			return False
		return value in vars

	def unary():
		return not unary() if accept('!') else primary()

	def logical_and():
		value = unary()
		while accept('&&'):
			right = unary()
			value = value and right
		return value

	def logical_or():
		value = logical_and()
		while accept('||'):
			right = logical_and()
			value = value or right
		return value

	result = logical_or()
	if pos[0] != len(tokens):
		raise ValueError('Trailing tokens in VPC condition: %s' % statement)
	return result

def project_key(l):
	for k in l.keys():
		if '$Project' in k:
			return k

def fix_dos_path( path ):
	path = path.replace('\\', '/')
	p = path.split('/')

	filename = p[-1]
	find_path = '/'.join(p[0:len(p)-1])
	if find_path == '': find_path = './'
	else: find_path += '/'

	if not os.path.exists(find_path):
		return find_path+filename

	dirlist = os.listdir(find_path)
	for file in dirlist:
		if file == filename:
			return find_path+file
		elif file.lower() == filename.lower():
			return find_path+file
	return find_path+filename

def expand_known_macros(path, basedir):
	# The game VPCs are parsed from game/server or game/client. VPC normally
	# defines these directory macros globally; Waf has to materialize them
	# before deciding whether an entry is a compilable source.
	path = re.sub(r'\$SRCDIR\b', lambda _: basedir, path, flags=re.IGNORECASE)
	path = re.sub(r'\$SRVSRCDIR\b', '.', path, flags=re.IGNORECASE)
	return path

def is_build_source(path):
	# VPC project folders also list link inputs and generated placeholders.
	# Waf's ``source`` attribute must contain only processable source/resource
	# files; unresolved macros and prebuilt libraries are handled elsewhere.
	if '$' in path:
		return False
	return os.path.splitext(path)[1].lower() in (
		'.c', '.cc', '.cpp', '.cxx', '.c++',
		'.s', '.asm', '.masm', '.rc'
	)

def parse_vpcs( env ,vpcs, basedir ):
	back_path = os.path.abspath('.')
	os.chdir(env.SUBPROJECT_PATH[0])

	sources = []
	defines = []
	includes = []

	for vpc in vpcs:
		f=open(vpc, 'r').read().replace('\\\n', ';')

		f = re.sub(r'//.*', '', f)
		l = f.split('\n')

		iBrackets = 0

		next_br = False
		ret = {}
		cur_key = ''

		for i in l:
			if i == '': continue

			s = match_statement.search(i)
			condition_defines = env.DEFINES + defines
			if getattr(env, 'GAMES', None) == 'csgo':
				condition_defines += ['CSGO=1', 'CSTRIKE15=1']
			if s and not compute_statement(condition_defines, s.group(0)):
				continue

			if i.startswith('$') and iBrackets == 0:
				ret.update({i:[]})
				cur_key = i
				next_br = True
			elif i == '{':
				iBrackets += 1
				next_br = False
			elif i == '}':
				iBrackets -= 1
			elif iBrackets > 0:
				ret[cur_key].append(i)

			if next_br:
				next_br = False

		key = project_key(ret)
		l=ret[key]

		for i in l:
			lower_i = i.lower()
			if '-$file' in lower_i and '.h"' not in lower_i:
				for k in i.split(';'):
					k = expand_known_macros(k, basedir)
					raw = k.split('"')[1]
					if not is_build_source(raw):
						continue
					s = fix_dos_path(raw)

					for j in range(len(sources)):
						if sources[j] == s:
							del sources[j]
							break

			elif '$file' in lower_i and '.h"' not in lower_i:
				for j in i.split(';'):
					j = expand_known_macros(j, basedir)
					raw = j.split('"')[1]
					if not is_build_source(raw):
						continue
					s = fix_dos_path(raw)
					sources.append(s)

		for i in ret['$Configuration']:
			if '$PreprocessorDefinitions' in i:
				i = i.replace('$BASE', '')
				s = i.split('"')[1]
				s = re.split(';|,', s)
				for j in s:
					if j != '' and j not in defines:
						defines.append(j)
			if '$AdditionalIncludeDirectories' in i:
				i = expand_known_macros(i.replace('$BASE', ''), basedir)
				s = i.split('"')[1]
				s = re.split(';|,', s)
				for j in s:
					j = j.replace('\\','/')
					if j != '' and j not in includes:
						includes.append(j)
	os.chdir(back_path)

	unique_sources = []
	seen_sources = set()
	for source in sources:
		key = os.path.normcase(os.path.normpath(source))
		if key not in seen_sources:
			seen_sources.add(key)
			unique_sources.append(source)

	return {'defines':defines, 'includes':includes, 'sources': unique_sources}
