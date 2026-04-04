/// <reference path="../pb_data/types.d.ts" />
migrate((app) => {
  const collection = app.findCollectionByNameOrId("pbc_4141841419")

  // add field
  collection.fields.addAt(1, new Field({
    "autogeneratePattern": "",
    "hidden": false,
    "id": "text3671908477",
    "max": 0,
    "min": 0,
    "name": "overall_verdict",
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
  collection.fields.addAt(3, new Field({
    "hidden": false,
    "id": "number3080093390",
    "max": null,
    "min": null,
    "name": "overall_score",
    "onlyInt": false,
    "presentable": false,
    "required": false,
    "system": false,
    "type": "number"
  }))

  // add field
  collection.fields.addAt(4, new Field({
    "hidden": false,
    "id": "json405522622",
    "maxSize": 0,
    "name": "report_json",
    "presentable": false,
    "required": false,
    "system": false,
    "type": "json"
  }))

  // add field
  collection.fields.addAt(5, new Field({
    "hidden": false,
    "id": "json2095011801",
    "maxSize": 0,
    "name": "improvement_tips",
    "presentable": false,
    "required": false,
    "system": false,
    "type": "json"
  }))

  // add field
  collection.fields.addAt(6, new Field({
    "hidden": false,
    "id": "json680782017",
    "maxSize": 0,
    "name": "gaps",
    "presentable": false,
    "required": false,
    "system": false,
    "type": "json"
  }))

  // add field
  collection.fields.addAt(7, new Field({
    "hidden": false,
    "id": "json2479893516",
    "maxSize": 0,
    "name": "strengths",
    "presentable": false,
    "required": false,
    "system": false,
    "type": "json"
  }))

  // add field
  collection.fields.addAt(8, new Field({
    "hidden": false,
    "id": "json3112632772",
    "maxSize": 0,
    "name": "phase_scores",
    "presentable": false,
    "required": false,
    "system": false,
    "type": "json"
  }))

  return app.save(collection)
}, (app) => {
  const collection = app.findCollectionByNameOrId("pbc_4141841419")

  // remove field
  collection.fields.removeById("text3671908477")

  // remove field
  collection.fields.removeById("text1631579359")

  // remove field
  collection.fields.removeById("number3080093390")

  // remove field
  collection.fields.removeById("json405522622")

  // remove field
  collection.fields.removeById("json2095011801")

  // remove field
  collection.fields.removeById("json680782017")

  // remove field
  collection.fields.removeById("json2479893516")

  // remove field
  collection.fields.removeById("json3112632772")

  return app.save(collection)
})
