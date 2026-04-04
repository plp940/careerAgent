/// <reference path="../pb_data/types.d.ts" />
migrate((app) => {
  const collection = app.findCollectionByNameOrId("pbc_2575675930")

  // add field
  collection.fields.addAt(1, new Field({
    "autogeneratePattern": "",
    "hidden": false,
    "id": "text1631579359",
    "max": 0,
    "min": 0,
    "name": "session_id",
    "pattern": "",
    "presentable": false,
    "primaryKey": false,
    "required": false,
    "system": false,
    "type": "text"
  }))

  // add field
  collection.fields.addAt(2, new Field({
    "autogeneratePattern": "",
    "hidden": false,
    "id": "text2063623452",
    "max": 0,
    "min": 0,
    "name": "status",
    "pattern": "",
    "presentable": false,
    "primaryKey": false,
    "required": false,
    "system": false,
    "type": "text"
  }))

  // add field
  collection.fields.addAt(3, new Field({
    "autogeneratePattern": "",
    "hidden": false,
    "id": "text2168693080",
    "max": 0,
    "min": 0,
    "name": "jd_text",
    "pattern": "",
    "presentable": false,
    "primaryKey": false,
    "required": false,
    "system": false,
    "type": "text"
  }))

  // add field
  collection.fields.addAt(4, new Field({
    "autogeneratePattern": "",
    "hidden": false,
    "id": "text3310183939",
    "max": 0,
    "min": 0,
    "name": "resume_text",
    "pattern": "",
    "presentable": false,
    "primaryKey": false,
    "required": false,
    "system": false,
    "type": "text"
  }))

  // add field
  collection.fields.addAt(5, new Field({
    "autogeneratePattern": "",
    "hidden": false,
    "id": "text1337919823",
    "max": 0,
    "min": 0,
    "name": "company",
    "pattern": "",
    "presentable": false,
    "primaryKey": false,
    "required": false,
    "system": false,
    "type": "text"
  }))

  // add field
  collection.fields.addAt(6, new Field({
    "autogeneratePattern": "",
    "hidden": false,
    "id": "text711640347",
    "max": 0,
    "min": 0,
    "name": "job_title",
    "pattern": "",
    "presentable": false,
    "primaryKey": false,
    "required": false,
    "system": false,
    "type": "text"
  }))

  // add field
  collection.fields.addAt(7, new Field({
    "hidden": false,
    "id": "json893757377",
    "maxSize": 0,
    "name": "projects_identified",
    "presentable": false,
    "required": false,
    "system": false,
    "type": "json"
  }))

  // add field
  collection.fields.addAt(8, new Field({
    "hidden": false,
    "id": "json2238802285",
    "maxSize": 0,
    "name": "resume_sections",
    "presentable": false,
    "required": false,
    "system": false,
    "type": "json"
  }))

  // add field
  collection.fields.addAt(9, new Field({
    "hidden": false,
    "id": "number363045327",
    "max": null,
    "min": null,
    "name": "current_phase",
    "onlyInt": false,
    "presentable": false,
    "required": false,
    "system": false,
    "type": "number"
  }))

  // add field
  collection.fields.addAt(10, new Field({
    "hidden": false,
    "id": "number1589472109",
    "max": null,
    "min": null,
    "name": "current_depth",
    "onlyInt": false,
    "presentable": false,
    "required": false,
    "system": false,
    "type": "number"
  }))

  return app.save(collection)
}, (app) => {
  const collection = app.findCollectionByNameOrId("pbc_2575675930")

  // remove field
  collection.fields.removeById("text1631579359")

  // remove field
  collection.fields.removeById("text2063623452")

  // remove field
  collection.fields.removeById("text2168693080")

  // remove field
  collection.fields.removeById("text3310183939")

  // remove field
  collection.fields.removeById("text1337919823")

  // remove field
  collection.fields.removeById("text711640347")

  // remove field
  collection.fields.removeById("json893757377")

  // remove field
  collection.fields.removeById("json2238802285")

  // remove field
  collection.fields.removeById("number363045327")

  // remove field
  collection.fields.removeById("number1589472109")

  return app.save(collection)
})
